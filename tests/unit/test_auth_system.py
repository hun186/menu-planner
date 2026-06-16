from pathlib import Path

import pytest
from fastapi import HTTPException

import importlib

from src.menu_planner.api.auth import dependencies
from src.menu_planner.api.auth.auth_store import AuthStore, AuthUser, create_token
from src.menu_planner.api.auth.models import (
    ApprovePayload,
    AuthPayload,
    ChangePasswordPayload,
    RecoverPasswordPayload,
    ResetPasswordPayload,
)

auth_store_module = importlib.import_module("src.menu_planner.api.auth.auth_store")
auth_routes_module = importlib.import_module("src.menu_planner.api.auth.auth_routes")


def _install_temp_auth_store(monkeypatch, tmp_path: Path) -> AuthStore:
    store = AuthStore(tmp_path / "auth_users.json")
    monkeypatch.setattr(dependencies, "AUTH_STORE", store)
    monkeypatch.setattr(auth_routes_module, "AUTH_STORE", store)
    monkeypatch.setattr(auth_store_module, "AUTH_STORE", store)
    return store


def _request():
    class Client:
        host = "127.0.0.1"

    class Request:
        client = Client()
        headers = {"user-agent": "pytest"}

    return Request()


def test_bootstrap_superuser_can_approve_pending_user(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_BOOTSTRAP_SUPERUSERS", '[{"username":"owner","password":"Password123!"}]')
    store = _install_temp_auth_store(monkeypatch, tmp_path)

    login = auth_routes_module.login(AuthPayload(username="owner", password="Password123!"), _request())
    owner_user = dependencies.current_user(f"Bearer {login['access_token']}")
    assert owner_user.role == "superuser"

    registered = auth_routes_module.register(AuthPayload(username="staff", password="StaffPass123!"), _request())
    assert "帳號申請已送出" in registered["message"]

    with pytest.raises(HTTPException) as denied:
        auth_routes_module.login(AuthPayload(username="staff", password="StaffPass123!"), _request())
    assert denied.value.status_code == 401

    approved = auth_routes_module.approve_user("staff", ApprovePayload(role="data_editor"), owner_user)
    assert approved["user"]["role"] == "data_editor"
    assert approved["user"]["status"] == "active"

    staff_login = auth_routes_module.login(AuthPayload(username="staff", password="StaffPass123!"), _request())
    assert staff_login["token_type"] == "bearer"


def test_new_role_permissions_and_token_invalidation(monkeypatch, tmp_path):
    store = _install_temp_auth_store(monkeypatch, tmp_path)

    with pytest.raises(HTTPException) as no_auth:
        dependencies.current_user(None)
    assert no_auth.value.status_code == 401

    store.register("owner", "OwnerPass123!")
    store.approve_user("owner", "superuser", approved_by="bootstrap")
    owner_token = create_token(AuthUser(username="owner", role="superuser", status="active"))
    owner = dependencies.require_superuser(user=dependencies.current_user(f"Bearer {owner_token}"))
    assert owner.username == "owner"

    store.register("staff", "StaffPass123!")
    store.approve_user("staff", "data_editor", approved_by="owner")
    staff_token = create_token(AuthUser(username="staff", role="data_editor", status="active"))
    staff_user = dependencies.require_data_editor(user=dependencies.current_user(f"Bearer {staff_token}"))
    assert staff_user.username == "staff"

    with pytest.raises(HTTPException) as backup_forbidden:
        dependencies.require_db_operator(user=dependencies.current_user(f"Bearer {staff_token}"))
    assert backup_forbidden.value.status_code == 403

    store.register("operator", "OperatorPass123!")
    store.approve_user("operator", "db_operator", approved_by="owner")
    backup_token = create_token(AuthUser(username="operator", role="db_operator", status="active"))
    db_operator = dependencies.require_db_operator(user=dependencies.current_user(f"Bearer {backup_token}"))
    assert db_operator.username == "operator"

    with pytest.raises(HTTPException) as forbidden:
        dependencies.require_superuser(user=dependencies.current_user(f"Bearer {backup_token}"))
    assert forbidden.value.status_code == 403

    changed = auth_routes_module.change_password(
        ChangePasswordPayload(current_password="StaffPass123!", new_password="NewStaffPass123!"),
        staff_user,
    )
    assert "既有 token 已失效" in changed["message"]
    with pytest.raises(HTTPException) as old_token_denied:
        dependencies.current_user(f"Bearer {staff_token}")
    assert old_token_denied.value.status_code == 401


def test_password_reset_logout_and_usage_stats(monkeypatch, tmp_path):
    store = _install_temp_auth_store(monkeypatch, tmp_path)
    store.register("owner", "OwnerPass123!")
    store.approve_user("owner", "superuser", approved_by="bootstrap")
    store.register("staff", "StaffPass123!")
    store.approve_user("staff", "data_reader", approved_by="owner")

    reset = auth_routes_module.issue_password_reset_token("staff", AuthUser("owner", "superuser", "active"))
    recovered = auth_routes_module.recover_password(
        RecoverPasswordPayload(username="staff", reset_token=reset["reset_token"], new_password="Recovered123!"),
        _request(),
    )
    assert recovered["user"]["username"] == "staff"

    login = auth_routes_module.login(AuthPayload(username="staff", password="Recovered123!"), _request())
    user = dependencies.current_user(f"Bearer {login['access_token']}")
    logout = auth_routes_module.logout(user, f"Bearer {login['access_token']}")
    assert "已登出" in logout["message"]
    with pytest.raises(HTTPException):
        dependencies.current_user(f"Bearer {login['access_token']}")


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
