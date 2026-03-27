import pytest
from fastapi import HTTPException

from src.menu_planner.api.routes import admin_catalog


class _FakeRepo:
    ingredient_exists_value = True
    price_exists_value = True
    delete_ingredient_count = 1
    deleted_prices = []
    deleted_ingredients = []
    merged_ingredients = []
    rename_dishes = []
    rename_ingredients = []

    def __init__(self, db_path: str):
        self.db_path = db_path

    def ingredient_exists(self, ingredient_id: str) -> bool:
        return self.ingredient_exists_value

    def price_exists(self, ingredient_id: str, price_date: str) -> bool:
        return self.price_exists_value

    def delete_price(self, ingredient_id: str, price_date: str):
        self.deleted_prices.append((ingredient_id, price_date))
        return 1

    def delete_ingredient(self, ingredient_id: str):
        self.deleted_ingredients.append(ingredient_id)
        return self.delete_ingredient_count

    def merge_ingredient(self, source_ingredient_id: str, target_ingredient_id: str):
        self.merged_ingredients.append((source_ingredient_id, target_ingredient_id))
        return {
            "merged_dish_count": 2,
            "merged_price_count": 1,
            "merged_inventory": True,
        }

    def dish_exists(self, dish_id: str) -> bool:
        return dish_id != "missing-dish"

    def rename_dish(self, source_dish_id: str, target_dish_id: str, body):
        if target_dish_id == "dish-exists":
            raise ValueError("目標菜色已存在：dish-exists")
        self.rename_dishes.append((source_dish_id, target_dish_id, body))
        return {
            "source_dish_id": source_dish_id,
            "target_dish_id": target_dish_id,
            "moved_ingredient_count": 3,
        }

    def rename_ingredient(self, source_ingredient_id: str, target_ingredient_id: str, body):
        if target_ingredient_id == "ing-exists":
            raise ValueError("目標食材已存在：ing-exists")
        self.rename_ingredients.append((source_ingredient_id, target_ingredient_id, body))
        return {
            "source_ingredient_id": source_ingredient_id,
            "target_ingredient_id": target_ingredient_id,
            "moved_dish_count": 2,
            "moved_price_count": 1,
            "moved_inventory": True,
        }


def test_delete_price_not_found_does_not_trigger_backup(monkeypatch):
    calls = {"backup": 0}

    _FakeRepo.ingredient_exists_value = True
    _FakeRepo.price_exists_value = False
    _FakeRepo.deleted_prices = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    with pytest.raises(HTTPException) as ex:
        admin_catalog.delete_price("ing-1", "2026-03-16", db_path="/tmp/menu.db")

    assert ex.value.status_code == 404
    assert calls["backup"] == 0
    assert _FakeRepo.deleted_prices == []


def test_delete_price_success_triggers_backup_once(monkeypatch):
    calls = {"backup": 0, "reason": None, "comment": None}

    _FakeRepo.ingredient_exists_value = True
    _FakeRepo.price_exists_value = True
    _FakeRepo.deleted_prices = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1
        calls["reason"] = kwargs.get("reason")
        calls["comment"] = kwargs.get("comment")

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    resp = admin_catalog.delete_price("ing-1", "2026-03-16", db_path="/tmp/menu.db")

    assert resp == {"ok": True}
    assert calls["backup"] == 1
    assert calls["reason"] == "ingredient_price_delete"
    assert calls["comment"] == "自動備份：食材價格刪除（ingredient_id=ing-1；price_date=2026-03-16）"
    assert _FakeRepo.deleted_prices == [("ing-1", "2026-03-16")]


def test_delete_ingredient_success_triggers_backup_once(monkeypatch):
    calls = {"backup": 0}

    _FakeRepo.ingredient_exists_value = True
    _FakeRepo.delete_ingredient_count = 1
    _FakeRepo.deleted_ingredients = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    resp = admin_catalog.delete_ingredient("ing-1", db_path="/tmp/menu.db")

    assert resp == {"ok": True}
    assert calls["backup"] == 1
    assert _FakeRepo.deleted_ingredients == ["ing-1"]


def test_merge_inventory_ingredient_success_triggers_backup_once(monkeypatch):
    calls = {"backup": 0, "reason": None, "comment": None}

    _FakeRepo.ingredient_exists_value = True
    _FakeRepo.merged_ingredients = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1
        calls["reason"] = kwargs.get("reason")
        calls["comment"] = kwargs.get("comment")

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    resp = admin_catalog.merge_inventory_ingredient(
        admin_catalog.IngredientMergeIn(source_ingredient_id="ing-a", target_ingredient_id="ing-b"),
        db_path="/tmp/menu.db",
    )

    assert resp == {
        "ok": True,
        "merged_dish_count": 2,
        "merged_price_count": 1,
        "merged_inventory": True,
    }
    assert calls["backup"] == 1
    assert calls["reason"] == "ingredient_merge:ing-a->ing-b"
    assert calls["comment"] == "自動備份：食材合併（source_ingredient_id=ing-a；target_ingredient_id=ing-b）"
    assert _FakeRepo.merged_ingredients == [("ing-a", "ing-b")]


def test_repo_with_backup_passes_reason_and_comment(monkeypatch):
    calls = {"reason": None, "comment": None}

    def _backup(_db_path: str, *args, **kwargs):
        calls["reason"] = kwargs.get("reason")
        calls["comment"] = kwargs.get("comment")

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)
    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    repo = admin_catalog.repo_with_backup(
        "/tmp/menu.db",
        reason="ingredient_upsert",
        comment="manual note",
    )

    assert isinstance(repo, _FakeRepo)
    assert calls["reason"] == "ingredient_upsert"
    assert calls["comment"] == "manual note"


def test_auto_backup_comment_skips_empty_details():
    comment = admin_catalog._auto_backup_comment("菜色刪除", dish_id="dish-1", note="")
    assert comment == "自動備份：菜色刪除（dish_id=dish-1）"


def test_merge_inventory_ingredient_same_source_and_target_does_not_trigger_backup(monkeypatch):
    calls = {"backup": 0}

    _FakeRepo.ingredient_exists_value = True
    _FakeRepo.merged_ingredients = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    with pytest.raises(HTTPException) as ex:
        admin_catalog.merge_inventory_ingredient(
            admin_catalog.IngredientMergeIn(source_ingredient_id="ing-a", target_ingredient_id="ing-a"),
            db_path="/tmp/menu.db",
        )

    assert ex.value.status_code == 400
    assert calls["backup"] == 0
    assert _FakeRepo.merged_ingredients == []


def test_list_db_backups_returns_descending_files(tmp_path):
    db = tmp_path / "menu.db"
    db.write_text("live-db", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old_file = backup_dir / "menu_20260320_120000_000001.db"
    new_file = backup_dir / "menu_20260320_120001_000001.db"
    old_file.write_text("old", encoding="utf-8")
    new_file.write_text("new", encoding="utf-8")

    rows = admin_catalog.list_db_backups(db_path=str(db))

    assert [x["filename"] for x in rows] == [new_file.name, old_file.name]
    assert all("size_bytes" in x and "modified_at" in x for x in rows)


def test_restore_db_backup_copies_file_and_triggers_pre_backup(monkeypatch, tmp_path):
    calls = {"backup": 0}
    db = tmp_path / "menu.db"
    db.write_text("live-db", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    src = backup_dir / "menu_20260320_120001_000001.db"
    src.write_text("snapshot-db", encoding="utf-8")

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    resp = admin_catalog.restore_db_backup(
        admin_catalog.BackupRestoreIn(backup_filename=src.name),
        db_path=str(db),
    )

    assert resp == {"ok": True, "restored_from": src.name}
    assert calls["backup"] == 1
    assert db.read_text(encoding="utf-8") == "snapshot-db"


def test_delete_db_backup_deletes_selected_file(tmp_path):
    db = tmp_path / "menu.db"
    db.write_text("live-db", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    target = backup_dir / "menu_20260320_120001_000001.db"
    target.write_text("snapshot-db", encoding="utf-8")

    resp = admin_catalog.delete_db_backup(target.name, db_path=str(db))

    assert resp == {"ok": True, "deleted": target.name}
    assert not target.exists()


def test_batch_delete_db_backups_by_single_day(tmp_path):
    db = tmp_path / "menu.db"
    db.write_text("live-db", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    keep = backup_dir / "menu_20260319_120001_000001.db"
    delete_a = backup_dir / "menu_20260320_120001_000001.db"
    delete_b = backup_dir / "menu_20260320_130001_000001.db"
    keep.write_text("k", encoding="utf-8")
    delete_a.write_text("a", encoding="utf-8")
    delete_b.write_text("b", encoding="utf-8")

    resp = admin_catalog.batch_delete_db_backups(
        admin_catalog.BackupBatchDeleteIn(date="2026-03-20"),
        db_path=str(db),
    )

    assert resp["ok"] is True
    assert resp["deleted_count"] == 2
    assert sorted(resp["deleted_files"]) == sorted([delete_a.name, delete_b.name])
    assert keep.exists()
    assert not delete_a.exists()
    assert not delete_b.exists()


def test_batch_delete_db_backups_by_date_range(tmp_path):
    db = tmp_path / "menu.db"
    db.write_text("live-db", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    keep = backup_dir / "menu_20260322_120001_000001.db"
    delete_a = backup_dir / "menu_20260320_120001_000001.db"
    delete_b = backup_dir / "menu_20260321_130001_000001.db"
    keep.write_text("k", encoding="utf-8")
    delete_a.write_text("a", encoding="utf-8")
    delete_b.write_text("b", encoding="utf-8")

    resp = admin_catalog.batch_delete_db_backups(
        admin_catalog.BackupBatchDeleteIn(date_from="2026-03-20", date_to="2026-03-21"),
        db_path=str(db),
    )

    assert resp["ok"] is True
    assert resp["deleted_count"] == 2
    assert keep.exists()
    assert not delete_a.exists()
    assert not delete_b.exists()


def test_batch_delete_db_backups_invalid_date_range_raises(tmp_path):
    db = tmp_path / "menu.db"
    db.write_text("live-db", encoding="utf-8")

    with pytest.raises(HTTPException) as ex:
        admin_catalog.batch_delete_db_backups(
            admin_catalog.BackupBatchDeleteIn(date_from="2026-03-21", date_to="2026-03-20"),
            db_path=str(db),
        )

    assert ex.value.status_code == 400
    assert ex.value.detail == "date_to 不可早於 date_from"


def test_get_db_backup_stats_warns_after_500mb(tmp_path):
    db = tmp_path / "menu.db"
    db.write_text("live-db", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    (backup_dir / "menu_20260320_120001_000001.db").write_bytes(b"a" * (300 * 1024 * 1024))
    (backup_dir / "menu_20260320_120002_000001.db").write_bytes(b"b" * (250 * 1024 * 1024))

    stats = admin_catalog.get_db_backup_stats(db_path=str(db))

    assert stats["count"] == 2
    assert stats["total_size_bytes"] == 550 * 1024 * 1024
    assert stats["warning_threshold_bytes"] == 500 * 1024 * 1024
    assert stats["is_over_warning_threshold"] is True


def test_update_db_backup_comment_updates_comment_and_preserves_reason(tmp_path):
    db = tmp_path / "menu.db"
    db.write_text("live-db", encoding="utf-8")
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    target = backup_dir / "menu_20260320_120001_000001.db"
    target.write_text("snapshot-db", encoding="utf-8")

    admin_catalog.upsert_backup_metadata(
        db_path=str(db),
        backup_filename=target.name,
        reason="admin_restore_pre_snapshot",
        comment="old",
    )

    resp = admin_catalog.update_db_backup_comment(
        target.name,
        admin_catalog.BackupCommentIn(comment="release-ready backup"),
        db_path=str(db),
    )

    assert resp == {"ok": True, "filename": target.name, "comment": "release-ready backup"}
    rows = admin_catalog.list_db_backups(db_path=str(db))
    assert rows[0]["action_reason"] == "admin_restore_pre_snapshot"
    assert rows[0]["comment"] == "release-ready backup"


def test_create_manual_db_backup_calls_backup_with_reason_and_comment(monkeypatch):
    calls = {"count": 0, "reason": None, "comment": None}

    def _backup(_db_path: str, *args, **kwargs):
        calls["count"] += 1
        calls["reason"] = kwargs.get("reason")
        calls["comment"] = kwargs.get("comment")

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    resp = admin_catalog.create_manual_db_backup(
        admin_catalog.BackupCreateIn(reason="manual_snapshot", comment="before holiday"),
        db_path="/tmp/menu.db",
    )

    assert resp == {"ok": True, "reason": "manual_snapshot", "comment": "before holiday"}
    assert calls["count"] == 1
    assert calls["reason"] == "manual_snapshot"
    assert calls["comment"] == "before holiday"


def test_rename_ingredient_success_triggers_backup_once(monkeypatch):
    calls = {"backup": 0}
    _FakeRepo.rename_ingredients = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    resp = admin_catalog.rename_ingredient(
        "ing-a",
        admin_catalog.IngredientRenameIn(
            target_id="ing-a-new",
            name="白米（新）",
            category="穀物",
            protein_group=None,
            default_unit="g",
        ),
        db_path="/tmp/menu.db",
    )

    assert resp == {
        "ok": True,
        "source_ingredient_id": "ing-a",
        "target_ingredient_id": "ing-a-new",
        "moved_dish_count": 2,
        "moved_price_count": 1,
        "moved_inventory": True,
    }
    assert calls["backup"] == 1
    assert _FakeRepo.rename_ingredients == [
        (
            "ing-a",
            "ing-a-new",
            {
                "name": "白米（新）",
                "category": "穀物",
                "protein_group": None,
                "default_unit": "g",
            },
        )
    ]


def test_rename_ingredient_same_id_does_not_trigger_backup(monkeypatch):
    calls = {"backup": 0}
    _FakeRepo.rename_ingredients = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    with pytest.raises(HTTPException) as ex:
        admin_catalog.rename_ingredient(
            "ing-a",
            admin_catalog.IngredientRenameIn(
                target_id="ing-a",
                name="白米",
                category="穀物",
                protein_group=None,
                default_unit="g",
            ),
            db_path="/tmp/menu.db",
        )

    assert ex.value.status_code == 400
    assert calls["backup"] == 0
    assert _FakeRepo.rename_ingredients == []


def test_rename_dish_success_triggers_backup_once(monkeypatch):
    calls = {"backup": 0}
    _FakeRepo.rename_dishes = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    resp = admin_catalog.rename_dish(
        "dish-a",
        admin_catalog.DishRenameIn(
            target_id="dish-a-new",
            name="菜色A 新版",
            role="main",
            cuisine="tw",
            meat_type=None,
            tags=["new"],
        ),
        db_path="/tmp/menu.db",
    )

    assert resp == {
        "ok": True,
        "source_dish_id": "dish-a",
        "target_dish_id": "dish-a-new",
        "moved_ingredient_count": 3,
    }
    assert calls["backup"] == 1
    assert _FakeRepo.rename_dishes == [
        (
            "dish-a",
            "dish-a-new",
            {
                "name": "菜色A 新版",
                "role": "main",
                "cuisine": "tw",
                "meat_type": None,
                "tags": ["new"],
            },
        )
    ]


def test_rename_dish_same_id_does_not_trigger_backup(monkeypatch):
    calls = {"backup": 0}
    _FakeRepo.rename_dishes = []

    monkeypatch.setattr(admin_catalog, "SQLiteAdminRepo", _FakeRepo)

    def _backup(_db_path: str, *args, **kwargs):
        calls["backup"] += 1

    monkeypatch.setattr(admin_catalog, "backup_before_modify", _backup)

    with pytest.raises(HTTPException) as ex:
        admin_catalog.rename_dish(
            "dish-a",
            admin_catalog.DishRenameIn(
                target_id="dish-a",
                name="菜色A",
                role="main",
                cuisine=None,
                meat_type=None,
                tags=[],
            ),
            db_path="/tmp/menu.db",
        )

    assert ex.value.status_code == 400
    assert calls["backup"] == 0
    assert _FakeRepo.rename_dishes == []
