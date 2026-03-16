import pytest
from fastapi import HTTPException

from src.menu_planner.api.routes import admin_catalog


class _FakeRepo:
    ingredient_exists_value = True
    price_exists_value = True
    deleted_prices = []

    def __init__(self, db_path: str):
        self.db_path = db_path

    def ingredient_exists(self, ingredient_id: str) -> bool:
        return self.ingredient_exists_value

    def price_exists(self, ingredient_id: str, price_date: str) -> bool:
        return self.price_exists_value

    def delete_price(self, ingredient_id: str, price_date: str):
        self.deleted_prices.append((ingredient_id, price_date))
        return 1


def test_delete_price_not_found_does_not_trigger_backup(monkeypatch):
    calls = {"backup": 0}

    _FakeRepo.ingredient_exists_value = True
    _FakeRepo.price_exists_value = False
    _FakeRepo.deleted_prices = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    with pytest.raises(HTTPException) as ex:
        admin_catalog.delete_price("ing-1", "2026-03-16", db_path="/tmp/menu.db")

    assert ex.value.status_code == 404
    assert calls["backup"] == 0
    assert _FakeRepo.deleted_prices == []


def test_delete_price_success_triggers_backup_once(monkeypatch):
    calls = {"backup": 0}

    _FakeRepo.ingredient_exists_value = True
    _FakeRepo.price_exists_value = True
    _FakeRepo.deleted_prices = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    resp = admin_catalog.delete_price("ing-1", "2026-03-16", db_path="/tmp/menu.db")

    assert resp == {"ok": True}
    assert calls["backup"] == 1
    assert _FakeRepo.deleted_prices == [("ing-1", "2026-03-16")]
