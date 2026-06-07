import sqlite3
from datetime import date

import pytest
from pydantic import ValidationError

from src.menu_planner.api.routes import admin_catalog
from src.menu_planner.db.admin_repo import SQLiteAdminRepo
from src.menu_planner.db.repo import Dish, SQLiteRepo
from src.menu_planner.engine.backtracking import fill_days_after_mains
from src.menu_planner.engine.features import DishFeatures


def _create_legacy_db(path):
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE ingredients (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              category TEXT NOT NULL,
              protein_group TEXT,
              default_unit TEXT NOT NULL
            );
            CREATE TABLE dishes (
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('main','side','veg','soup','fruit')),
              cuisine TEXT,
              meat_type TEXT,
              tags_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE dish_ingredients (
              dish_id TEXT NOT NULL,
              ingredient_id TEXT NOT NULL,
              qty REAL NOT NULL,
              unit TEXT NOT NULL,
              PRIMARY KEY (dish_id, ingredient_id)
            );
            CREATE TABLE ingredient_prices (
              ingredient_id TEXT NOT NULL,
              price_date TEXT NOT NULL,
              price_per_unit REAL NOT NULL,
              unit TEXT NOT NULL,
              PRIMARY KEY (ingredient_id, price_date)
            );
            CREATE TABLE inventory (
              ingredient_id TEXT PRIMARY KEY,
              qty_on_hand REAL NOT NULL,
              unit TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              expiry_date TEXT
            );
            INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json)
            VALUES ('legacy', '舊菜色', 'main', NULL, 'chicken', '[]');
            """
        )


def _has_prep_column(path):
    with sqlite3.connect(path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(dishes)").fetchall()]
    return "prep_minutes" in columns


def _mk_dish(dish_id: str, role: str, prep_minutes: int) -> Dish:
    return Dish(
        id=dish_id,
        name=dish_id,
        role=role,
        cuisine="tw",
        meat_type="pork" if role == "main" else None,
        tags=[],
        prep_minutes=prep_minutes,
    )


def _mk_feat(dish_id: str, role: str, meat_type: str | None = None) -> DishFeatures:
    return DishFeatures(
        dish_id=dish_id,
        role=role,
        meat_type=meat_type,
        cuisine="tw",
        cost_per_serving=10.0,
        inventory_hit_ratio=0.0,
        near_expiry_days_min=None,
        used_inventory_ingredients=[],
    )


def test_legacy_db_without_prep_column_reads_default_zero_without_migrating(tmp_path):
    db_path = tmp_path / "legacy.db"
    _create_legacy_db(db_path)

    dishes = SQLiteRepo(str(db_path)).fetch_dishes()
    admin_payload = SQLiteAdminRepo(str(db_path)).list_dishes()

    assert dishes[0].prep_minutes == 0
    assert admin_payload["items"][0]["prep_minutes"] == 0
    assert _has_prep_column(db_path) is False


def test_dish_upsert_migrates_and_persists_prep_minutes(tmp_path):
    db_path = tmp_path / "legacy.db"
    _create_legacy_db(db_path)

    body = admin_catalog.DishUpsert(
        name="舊菜色更新",
        role="main",
        cuisine=None,
        meat_type="chicken",
        tags=[],
        allowed_weekdays=[1, 3, 5],
        prep_minutes=25,
    )

    resp = admin_catalog.upsert_dish("legacy", body, db_path=str(db_path))

    assert resp == {"ok": True, "id": "legacy"}
    assert _has_prep_column(db_path) is True
    assert SQLiteRepo(str(db_path)).fetch_dishes()[0].prep_minutes == 25

    backup_dir = tmp_path / "backups"
    backup_files = list(backup_dir.glob("legacy_*.db"))
    assert len(backup_files) == 1
    assert _has_prep_column(backup_files[0]) is False


def test_dish_upsert_rejects_negative_prep_minutes():
    with pytest.raises(ValidationError):
        admin_catalog.DishUpsert(name="壞資料", role="main", prep_minutes=-1)


def test_fill_days_uses_shorter_candidate_to_stay_under_prep_limit():
    mains = ["main_a"]
    sides = [_mk_dish("side_heavy", "side", 30), _mk_dish("side_light", "side", 10)]
    feat = {
        "main_a": _mk_feat("main_a", "main", "pork"),
        "side_heavy": _mk_feat("side_heavy", "side"),
        "side_light": _mk_feat("side_light", "side"),
    }
    main_dishes = [_mk_dish("main_a", "main", 40)]

    plan_days, _score, explanations, errors = fill_days_after_mains(
        horizon_days=1,
        main_ids=mains,
        sides=sides,
        vegs=[],
        soups=[],
        fruits=[],
        feat=feat,
        hard={"seed": 7, "prep_time_limit_minutes": 50, "cost_range_per_person_per_day": {"min": 0, "max": 999}},
        weights={},
        soft={},
        start_date=date(2026, 6, 1),
        role_counts_by_day=[{"main": 1, "side": 1, "veg": 0, "soup": 0, "fruit": 0, "noodle": 0}],
        mains=main_dishes,
    )

    assert errors == []
    assert plan_days[0].sides == ["side_light"]
    assert explanations[0]["prep_minutes_total"] == 50
    assert explanations[0]["prep_minutes_limit"] == 50


def test_fill_days_returns_clear_prep_limit_error_when_no_solution():
    mains = ["main_a"]
    sides = [_mk_dish("side_heavy", "side", 30)]
    feat = {
        "main_a": _mk_feat("main_a", "main", "pork"),
        "side_heavy": _mk_feat("side_heavy", "side"),
    }
    main_dishes = [_mk_dish("main_a", "main", 40)]

    _plan_days, _score, _explanations, errors = fill_days_after_mains(
        horizon_days=1,
        main_ids=mains,
        sides=sides,
        vegs=[],
        soups=[],
        fruits=[],
        feat=feat,
        hard={"seed": 7, "prep_time_limit_minutes": 50, "cost_range_per_person_per_day": {"min": 0, "max": 999}},
        weights={},
        soft={},
        start_date=date(2026, 6, 1),
        role_counts_by_day=[{"main": 1, "side": 1, "veg": 0, "soup": 0, "fruit": 0, "noodle": 0}],
        mains=main_dishes,
    )

    assert errors
    assert errors[0]["code"] == "PREP_TIME_LIMIT_EXCEEDED"
    assert "備菜時間上限" in errors[0]["message"]
    assert "調高每日備菜時間上限" in errors[0]["details"]["hint"]
