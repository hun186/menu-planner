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


def test_default_auth_store_falls_back_to_temp_store_when_project_store_is_unwritable(monkeypatch, tmp_path):
    auth_store_module = importlib.import_module("src.menu_planner.api.auth.auth_store")
    project_store = tmp_path / "readonly-project" / ".auth_users.json"
    fallback_store = tmp_path / "tmp-auth" / ".auth_users.json"
    original_ensure_file = auth_store_module.AuthStore._ensure_file

    def fake_ensure_file(self):
        if self.path == project_store:
            raise OSError("read-only file system")
        return original_ensure_file(self)

    monkeypatch.delenv("AUTH_USERS_FILE", raising=False)
    monkeypatch.setattr(auth_store_module, "_auth_file", lambda: project_store)
    monkeypatch.setattr(auth_store_module, "_fallback_auth_file", lambda: fallback_store)
    monkeypatch.setattr(auth_store_module.AuthStore, "_ensure_file", fake_ensure_file)

    with pytest.warns(RuntimeWarning, match="ephemeral store"):
        store = auth_store_module.AuthStore()

    assert store.path == fallback_store
    assert fallback_store.exists()


def test_explicit_auth_store_path_does_not_fall_back_on_write_error(monkeypatch, tmp_path):
    auth_store_module = importlib.import_module("src.menu_planner.api.auth.auth_store")
    explicit_store = tmp_path / "explicit" / "auth_users.json"

    def fake_ensure_file(self):
        raise OSError("read-only file system")

    monkeypatch.setattr(auth_store_module.AuthStore, "_ensure_file", fake_ensure_file)

    with pytest.raises(OSError, match="read-only file system"):
        auth_store_module.AuthStore(explicit_store)
