from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import time
import warnings
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any

PBKDF2_ITERATIONS = 260_000
ALLOWED_ROLES = {"user", "manager", "backup_manager", "superuser"}


def _env_value(name: str) -> str:
    return (os.getenv(name) or "").strip()


TOKEN_TTL_SECONDS = int(_env_value("AUTH_TOKEN_TTL_SECONDS") or str(60 * 60 * 12))


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: str
    status: str


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _project_root() -> Path:
    configured = _env_value("AUTH_PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.cwd().resolve()


def _auth_config_dir() -> Path:
    return _project_root() / "config" / "auth"


def _bootstrap_superusers_file() -> Path:
    configured = _env_value("AUTH_BOOTSTRAP_SUPERUSERS_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    return _auth_config_dir() / "bootstrap_superusers.json"


def _auth_file() -> Path:
    configured = _env_value("AUTH_USERS_FILE")
    if configured:
        return Path(configured).expanduser().resolve()
    return _project_root() / ".auth_users.json"


def _fallback_auth_file() -> Path:
    return Path(tempfile.gettempdir()).resolve() / "menu-planner" / ".auth_users.json"


def _token_secret() -> bytes:
    secret = (_env_value("AUTH_SECRET") or os.getenv("SECRET_KEY") or "").strip()
    if not secret:
        secret = "menu-planner-auth-development-secret-change-me"
    return secret.encode("utf-8")


def _hash_password(password: str, *, salt: str | None = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        PBKDF2_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest}"


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, iterations_s, salt, expected = password_hash.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt),
            int(iterations_s),
        ).hex()
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _collect_superusers_from_parsed(parsed: Any) -> list[dict[str, str]]:
    if isinstance(parsed, dict):
        parsed = parsed.get("superusers") or parsed.get("users") or []
    users: list[dict[str, str]] = []
    if not isinstance(parsed, list):
        return users
    for item in parsed:
        if not isinstance(item, dict):
            continue
        username = str(item.get("username") or "").strip()
        password = str(item.get("password") or "")
        if username and password:
            users.append({"username": username, "password": password})
    return users


def _load_bootstrap_superusers() -> list[dict[str, str]]:
    users: list[dict[str, str]] = []
    fixed_file = _bootstrap_superusers_file()
    if fixed_file.exists():
        try:
            with fixed_file.open("r", encoding="utf-8") as f:
                users.extend(_collect_superusers_from_parsed(json.load(f)))
        except (OSError, json.JSONDecodeError):
            pass
    raw_json = _env_value("AUTH_BOOTSTRAP_SUPERUSERS")
    if raw_json:
        try:
            users.extend(_collect_superusers_from_parsed(json.loads(raw_json)))
        except json.JSONDecodeError:
            pass
    single_username = _env_value("AUTH_BOOTSTRAP_SUPERUSER_USERNAME")
    single_password = _env_value("AUTH_BOOTSTRAP_SUPERUSER_PASSWORD")
    if single_username and single_password:
        users.append({"username": single_username, "password": single_password})
    deduped = {item["username"]: item for item in users}
    return list(deduped.values())


class AuthStore:
    def __init__(self, path: Path | None = None) -> None:
        self._lock = RLock()
        self._explicit_path = path is not None or bool(_env_value("AUTH_USERS_FILE"))
        self.path = path or _auth_file()
        self._prepare_storage()
        self.ensure_bootstrap_superusers()

    def _prepare_storage(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_file()
        except OSError as exc:
            if self._explicit_path:
                raise
            fallback = _fallback_auth_file()
            warnings.warn(
                f"Auth user store {self.path} is not writable ({exc}); using ephemeral store {fallback}.",
                RuntimeWarning,
                stacklevel=2,
            )
            self.path = fallback
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_file()

    def _ensure_file(self) -> None:
        if not self.path.exists():
            self._write({"users": {}, "created_at": _utc_now(), "updated_at": _utc_now()})

    def _read(self) -> dict[str, Any]:
        with self._lock:
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {"users": {}}
            except json.JSONDecodeError:
                data = {"users": {}}
            if not isinstance(data, dict):
                data = {"users": {}}
            if not isinstance(data.get("users"), dict):
                data["users"] = {}
            return data

    def _write(self, data: dict[str, Any]) -> None:
        with self._lock:
            data["updated_at"] = _utc_now()
            fd, tmp_name = tempfile.mkstemp(prefix=".auth_users.", suffix=".json", dir=str(self.path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
                    f.write("\n")
                os.replace(tmp_name, self.path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)

    def ensure_bootstrap_superusers(self) -> None:
        bootstrap_users = _load_bootstrap_superusers()
        if not bootstrap_users:
            return
        data = self._read()
        users = data["users"]
        changed = False
        for item in bootstrap_users:
            username = item["username"]
            if username in users:
                continue
            users[username] = {
                "username": username,
                "password_hash": _hash_password(item["password"]),
                "role": "superuser",
                "status": "active",
                "created_at": _utc_now(),
                "approved_at": _utc_now(),
                "approved_by": "bootstrap",
                "full_name": None,
                "department": None,
                "note": "bootstrap superuser",
            }
            changed = True
        if changed:
            self._write(data)

    def has_users(self) -> bool:
        return bool(self._read().get("users"))

    def list_users(self) -> list[dict[str, Any]]:
        users = self._read().get("users") or {}
        out = []
        for user in users.values():
            clean = dict(user)
            clean.pop("password_hash", None)
            out.append(clean)
        return sorted(out, key=lambda x: str(x.get("created_at") or ""), reverse=True)

    def get_user(self, username: str) -> dict[str, Any] | None:
        user = self._read().get("users", {}).get(username)
        return dict(user) if isinstance(user, dict) else None

    def register(self, username: str, password: str, *, full_name: str | None = None, department: str | None = None, note: str | None = None) -> dict[str, Any]:
        username = username.strip()
        if not username:
            raise ValueError("帳號不可為空。")
        if not password:
            raise ValueError("密碼不可為空。")
        data = self._read()
        users = data["users"]
        if username in users:
            raise ValueError("帳號已存在。")
        is_first_user = not bool(users)
        now = _utc_now()
        users[username] = {
            "username": username,
            "password_hash": _hash_password(password),
            "role": "superuser" if is_first_user else "user",
            "status": "active" if is_first_user else "pending",
            "created_at": now,
            "approved_at": now if is_first_user else None,
            "approved_by": "first-user" if is_first_user else None,
            "full_name": (full_name or "").strip() or None,
            "department": (department or "").strip() or None,
            "note": (note or "").strip() or None,
        }
        self._write(data)
        clean = dict(users[username])
        clean.pop("password_hash", None)
        return clean

    def authenticate(self, username: str, password: str) -> AuthUser | None:
        stored = self.get_user(username.strip())
        if not stored or not _verify_password(password, str(stored.get("password_hash") or "")):
            return None
        return AuthUser(username=str(stored["username"]), role=str(stored.get("role") or "user"), status=str(stored.get("status") or "pending"))

    def approve_user(self, username: str, role: str, *, approved_by: str) -> dict[str, Any]:
        role = role.strip()
        if role not in ALLOWED_ROLES:
            raise ValueError("不支援的角色。")
        data = self._read()
        users = data["users"]
        if username not in users:
            raise KeyError("找不到使用者。")
        users[username]["role"] = role
        users[username]["status"] = "active"
        users[username]["approved_at"] = _utc_now()
        users[username]["approved_by"] = approved_by
        self._write(data)
        clean = dict(users[username])
        clean.pop("password_hash", None)
        return clean

    def reject_user(self, username: str, *, rejected_by: str) -> dict[str, Any]:
        data = self._read()
        users = data["users"]
        if username not in users:
            raise KeyError("找不到使用者。")
        users[username]["status"] = "rejected"
        users[username]["rejected_at"] = _utc_now()
        users[username]["rejected_by"] = rejected_by
        self._write(data)
        clean = dict(users[username])
        clean.pop("password_hash", None)
        return clean

    def delete_user(self, username: str) -> dict[str, Any]:
        data = self._read()
        users = data["users"]
        if username not in users:
            raise KeyError("找不到使用者。")
        deleted = users.pop(username)
        self._write(data)
        clean = dict(deleted)
        clean.pop("password_hash", None)
        return clean


def create_token(user: AuthUser) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user.username, "role": user.role, "iat": int(time.time()), "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(payload, separators=(',', ':')).encode())}"
    sig = hmac.new(_token_secret(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(sig)}"


def parse_token(token: str) -> dict[str, Any] | None:
    try:
        head_b64, payload_b64, sig_b64 = token.split(".", 2)
        signing_input = f"{head_b64}.{payload_b64}"
        expected = _b64url(hmac.new(_token_secret(), signing_input.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(sig_b64, expected):
            return None
        payload = json.loads(_b64url_decode(payload_b64))
        if int(payload.get("exp") or 0) < int(time.time()):
            return None
        return payload if isinstance(payload, dict) else None
    except Exception:
        return None


AUTH_STORE = AuthStore()
