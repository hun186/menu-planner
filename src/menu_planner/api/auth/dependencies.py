from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status

from .auth_store import AUTH_STORE, AuthUser, parse_token


def bearer_token(authorization: str | None) -> str:
    if not isinstance(authorization, str) or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="請先登入。")
    return authorization.split(" ", 1)[1].strip()


def current_user(authorization: str | None = Header(default=None)) -> AuthUser:
    payload = parse_token(bearer_token(authorization))
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登入已失效，請重新登入。")
    username = str(payload.get("sub") or "")
    stored = AUTH_STORE.get_user(username)
    if not stored or stored.get("status") != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="帳號尚未啟用。")
    return AuthUser(username=username, role=str(stored.get("role") or "user"), status="active")


def require_active_user(user: AuthUser = Depends(current_user)) -> AuthUser:
    return user


def require_data_editor(authorization: str | None = Header(default=None)) -> AuthUser:
    return current_user(authorization)


def require_backup_manager(authorization: str | None = Header(default=None)) -> AuthUser:
    user = current_user(authorization)
    if user.role not in {"backup_manager", "superuser"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要備份管理員或超級使用者權限。")
    return user


def require_superuser(user: AuthUser = Depends(current_user)) -> AuthUser:
    if user.role != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要超級使用者權限。")
    return user


def require_admin_user(authorization: str | None = Header(default=None)) -> AuthUser:
    return require_superuser(current_user(authorization))
