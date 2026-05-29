import sqlite3

from src.menu_planner.api.routes import admin_catalog
from src.menu_planner.db.admin_repo import SQLiteAdminRepo
from src.menu_planner.db.repo import SQLiteRepo


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
            """
        )
        conn.execute(
            "INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json) VALUES(?, ?, ?, ?, ?, ?)",
            ("legacy", "舊菜色", "main", None, "chicken", "[]"),
        )


def _has_allowed_weekdays_column(path):
    with sqlite3.connect(path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(dishes)").fetchall()]
    return "allowed_weekdays_json" in columns


def test_reading_legacy_db_uses_full_week_without_migrating(tmp_path):
    db_path = tmp_path / "legacy.db"
    _create_legacy_db(db_path)

    dishes = SQLiteRepo(str(db_path)).fetch_dishes()
    admin_payload = SQLiteAdminRepo(str(db_path)).list_dishes()

    assert dishes[0].allowed_weekdays == [1, 2, 3, 4, 5, 6, 7]
    assert admin_payload["items"][0]["allowed_weekdays"] == [1, 2, 3, 4, 5, 6, 7]
    assert _has_allowed_weekdays_column(db_path) is False


def test_dish_write_on_legacy_db_backs_up_then_migrates_and_persists_field(tmp_path):
    db_path = tmp_path / "legacy.db"
    _create_legacy_db(db_path)

    body = admin_catalog.DishUpsert(
        name="舊菜色更新",
        role="main",
        cuisine=None,
        meat_type="chicken",
        tags=[],
        allowed_weekdays=[1, 3, 5],
    )

    resp = admin_catalog.upsert_dish("legacy", body, db_path=str(db_path))

    assert resp == {"ok": True, "id": "legacy"}
    assert _has_allowed_weekdays_column(db_path) is True
    assert SQLiteRepo(str(db_path)).fetch_dishes()[0].allowed_weekdays == [1, 3, 5]

    backup_dir = tmp_path / "backups"
    backup_files = list(backup_dir.glob("legacy_*.db"))
    assert len(backup_files) == 1
    assert _has_allowed_weekdays_column(backup_files[0]) is False


def test_planner_merges_catalog_weekday_rules_without_overriding_user_config():
    from src.menu_planner.db.repo import Dish
    from src.menu_planner.engine.planner import _merge_dish_allowed_weekdays_from_catalog

    hard = {"dish_allowed_weekdays": {"db_rule": [2]}}
    dishes = [
        Dish("db_rule", "資料庫菜色", "main", None, None, [], [1, 3]),
        Dish("new_rule", "新增規則", "side", None, None, [], [4]),
        Dish("full_week", "全週菜色", "soup", None, None, [], [1, 2, 3, 4, 5, 6, 7]),
    ]

    _merge_dish_allowed_weekdays_from_catalog(hard, dishes)

    assert hard["dish_allowed_weekdays"]["db_rule"] == [2]
    assert hard["dish_allowed_weekdays"]["new_rule"] == [4]
    assert "full_week" not in hard["dish_allowed_weekdays"]
