from pathlib import Path

import pytest
from fastapi import HTTPException

import importlib

from src.menu_planner.api.auth import dependencies
from src.menu_planner.api.auth.auth_store import AuthStore, create_token
from src.menu_planner.api.auth.models import ApprovePayload, AuthPayload

auth_router_module = importlib.import_module("src.menu_planner.api.auth.router")


def _install_temp_auth_store(monkeypatch, tmp_path: Path) -> AuthStore:
    store = AuthStore(tmp_path / "auth_users.json")
    monkeypatch.setattr(dependencies, "AUTH_STORE", store)
    monkeypatch.setattr(auth_router_module, "AUTH_STORE", store)
    return store


def test_first_registered_user_is_superuser_and_can_approve_pending_user(monkeypatch, tmp_path):
    _install_temp_auth_store(monkeypatch, tmp_path)

    first = auth_router_module.register(AuthPayload(username="owner", password="pw1"))
    assert first["user"]["role"] == "superuser"
    assert first["user"]["status"] == "active"

    login = auth_router_module.login(AuthPayload(username="owner", password="pw1"))
    owner_user = dependencies.current_user(f"Bearer {login['access_token']}")

    pending = auth_router_module.register(AuthPayload(username="staff", password="pw2"))
    assert pending["user"]["status"] == "pending"

    with pytest.raises(HTTPException) as denied:
        auth_router_module.login(AuthPayload(username="staff", password="pw2"))
    assert denied.value.status_code == 403

    approved = auth_router_module.approve_user("staff", ApprovePayload(role="manager"), owner_user)
    assert approved["user"]["role"] == "manager"
    assert approved["user"]["status"] == "active"

    staff_login = auth_router_module.login(AuthPayload(username="staff", password="pw2"))
    assert staff_login["token_type"] == "bearer"


def test_require_admin_user_accepts_only_superuser_token(monkeypatch, tmp_path):
    store = _install_temp_auth_store(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as no_auth:
        dependencies.require_admin_user()
    assert no_auth.value.status_code == 401

    owner = store.register("owner", "pw1")
    token = create_token(dependencies.AuthUser(username=owner["username"], role=owner["role"], status=owner["status"]))
    user = dependencies.require_admin_user(authorization=f"Bearer {token}")
    assert user is not None
    assert user.username == "owner"

    staff = store.register("staff", "pw2")
    store.approve_user(staff["username"], "user", approved_by="owner")
    staff_token = create_token(dependencies.AuthUser(username="staff", role="user", status="active"))
    with pytest.raises(HTTPException) as forbidden:
        dependencies.require_admin_user(authorization=f"Bearer {staff_token}")
    assert forbidden.value.status_code == 403
