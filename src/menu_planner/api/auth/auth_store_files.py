from __future__ import annotations

import json
import os
import secrets
import shutil
import tempfile
import warnings
from pathlib import Path
from threading import RLock
from typing import Any

from .auth_support import (
    AUTH_BACKUP_LIMIT,
    AUTH_STORE_BACKUP_LIMIT,
    LOGIN_AUDIT_LIMIT,
    _auth_audit_file,
    _now_ts,
    _utc_now,
)


def normalize_auth_store_data(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data.get("users"), dict):
        data["users"] = {}
    if not isinstance(data.get("token_denylist"), dict):
        data["token_denylist"] = {}
    if not isinstance(data.get("password_reset_tokens"), dict):
        data["password_reset_tokens"] = {}
    data.pop("login_audit", None)
    return data


class AuthStoreFiles:
    def __init__(self, path: Path, lock: RLock) -> None:
        self.path = path
        self.audit_path = _auth_audit_file(path)
        self._lock = lock

    def retarget(self, path: Path) -> None:
        self.path = path
        self.audit_path = _auth_audit_file(path)

    def ensure_file(self) -> None:
        if self.path.exists():
            return
        self.write(normalize_auth_store_data({"users": {}, "created_at": _utc_now(), "updated_at": _utc_now()}))

    def read(self) -> dict[str, Any]:
        with self._lock:
            try:
                with self.path.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except FileNotFoundError:
                data = {"users": {}}
            except json.JSONDecodeError as exc:
                data = self._recover_from_corrupt_file(exc)
            if not isinstance(data, dict):
                self._backup_corrupt_file("non_object_json")
                data = {"users": {}}
            return normalize_auth_store_data(data)

    def write(self, data: dict[str, Any]) -> None:
        with self._lock:
            data = normalize_auth_store_data(data)
            data["updated_at"] = _utc_now()
            self._backup_current_store_file()
            fd, tmp_name = tempfile.mkstemp(prefix=".auth_users.", suffix=".json", dir=str(self.path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
                    f.write("\n")
                os.replace(tmp_name, self.path)
            finally:
                if os.path.exists(tmp_name):
                    os.unlink(tmp_name)

    def migrate_inline_login_audit(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        if not isinstance(data, dict):
            return
        inline_audit = data.get("login_audit")
        if not isinstance(inline_audit, list):
            return
        existing_events = self.list_login_audit(LOGIN_AUDIT_LIMIT) if self.audit_path.exists() else []
        if not existing_events:
            for item in inline_audit[-LOGIN_AUDIT_LIMIT:]:
                if isinstance(item, dict):
                    self.append_login_audit_event(item)
        data.pop("login_audit", None)
        self.write(data)

    def record_login_audit(self, username: str, *, success: bool, reason: str, role: str | None = None, status_value: str | None = None, client_host: str | None = None, user_agent: str | None = None) -> None:
        self.append_login_audit_event({
            "ts": _utc_now(),
            "username": username,
            "success": success,
            "reason": reason,
            "role": role,
            "status": status_value,
            "client_host": client_host,
            "user_agent": user_agent,
        })

    def append_login_audit_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False, sort_keys=True))
                f.write("\n")
            self._prune_login_audit_file()

    def list_login_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(limit, LOGIN_AUDIT_LIMIT))
        events: list[dict[str, Any]] = []
        if self.audit_path.exists():
            try:
                with self.audit_path.open("r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(item, dict):
                            events.append(item)
            except OSError:
                pass
        return events[-limit:]

    def _backup_corrupt_file(self, reason: str) -> Path | None:
        if not self.path.exists():
            return None
        backup = self.path.with_name(f"{self.path.name}.corrupt-{_now_ts()}-{reason}.bak")
        try:
            os.replace(self.path, backup)
        except OSError:
            return None
        for old in sorted(self.path.parent.glob(f"{self.path.name}.corrupt-*.bak"), key=lambda item: item.stat().st_mtime, reverse=True)[AUTH_BACKUP_LIMIT:]:
            try:
                old.unlink()
            except OSError:
                pass
        return backup

    def _recover_from_corrupt_file(self, exc: json.JSONDecodeError) -> dict[str, Any]:
        backup = self._backup_corrupt_file("json_decode")
        warnings.warn(
            f"Auth user store {self.path} is corrupt ({exc}); moved to {backup} and recreated an empty store.",
            RuntimeWarning,
            stacklevel=2,
        )
        return {"users": {}, "created_at": _utc_now()}

    def _backup_current_store_file(self) -> Path | None:
        if not self.path.exists() or AUTH_STORE_BACKUP_LIMIT <= 0:
            return None
        backup_dir = self.path.with_name(f"{self.path.name}.versions")
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / f"{self.path.name}.{_now_ts()}.{secrets.token_hex(4)}.bak"
            shutil.copy2(self.path, backup)
        except OSError:
            return None
        self._prune_version_backups(backup_dir)
        return backup

    def _prune_version_backups(self, backup_dir: Path) -> None:
        try:
            backups = sorted(
                (item for item in backup_dir.glob(f"{self.path.name}.*.bak") if item.is_file()),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
        except OSError:
            return
        for old in backups[AUTH_STORE_BACKUP_LIMIT:]:
            try:
                old.unlink()
            except OSError:
                pass

    def _prune_login_audit_file(self) -> None:
        if LOGIN_AUDIT_LIMIT <= 0 or not self.audit_path.exists():
            return
        try:
            lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        if len(lines) <= LOGIN_AUDIT_LIMIT:
            return
        fd, tmp_name = tempfile.mkstemp(prefix=".auth_audit.", suffix=".jsonl", dir=str(self.audit_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for line in lines[-LOGIN_AUDIT_LIMIT:]:
                    f.write(line)
                    f.write("\n")
            os.replace(tmp_name, self.audit_path)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
