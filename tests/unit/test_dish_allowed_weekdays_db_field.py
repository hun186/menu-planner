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


def test_noodle_role_schema_migration_preserves_dish_rows_and_foreign_keys(tmp_path):
    db_path = tmp_path / "legacy_fk.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
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
              PRIMARY KEY (dish_id, ingredient_id),
              FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
              FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT
            );
            INSERT INTO ingredients(id, name, category, protein_group, default_unit)
            VALUES ('ing1', '雞肉', 'protein', NULL, 'g');
            INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json)
            VALUES ('dish1', '雞肉主菜', 'main', 'tw', 'chicken', '[]');
            INSERT INTO dish_ingredients(dish_id, ingredient_id, qty, unit)
            VALUES ('dish1', 'ing1', 100, 'g');
            """
        )

    SQLiteAdminRepo(str(db_path)).ensure_compatible_schema()

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        assert conn.execute("SELECT id, name, role FROM dishes").fetchall() == [
            ("dish1", "雞肉主菜", "main")
        ]
        assert conn.execute("SELECT dish_id, ingredient_id, qty, unit FROM dish_ingredients").fetchall() == [
            ("dish1", "ing1", 100.0, "g")
        ]
        fk_targets = [row[2] for row in conn.execute("PRAGMA foreign_key_list(dish_ingredients)").fetchall()]
        assert "dishes" in fk_targets
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        conn.execute(
            "INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json, allowed_weekdays_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("noodle1", "水餃", "noodle", "tw", None, "[]", "[1,2,3,4,5,6,7]"),
        )


def test_noodle_role_schema_migration_ignores_preexisting_orphan_fk_rows(tmp_path):
    db_path = tmp_path / "legacy_fk_orphan.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
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
              PRIMARY KEY (dish_id, ingredient_id),
              FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
              FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT
            );
            INSERT INTO ingredients(id, name, category, protein_group, default_unit)
            VALUES ('ing1', '雞肉', 'protein', NULL, 'g');
            INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json)
            VALUES ('dish1', '雞肉主菜', 'main', 'tw', 'chicken', '[]');
            INSERT INTO dish_ingredients(dish_id, ingredient_id, qty, unit)
            VALUES ('dish1', 'ing1', 100, 'g');
            INSERT INTO dish_ingredients(dish_id, ingredient_id, qty, unit)
            VALUES ('missing_dish', 'ing1', 50, 'g');
            """
        )

    SQLiteAdminRepo(str(db_path)).ensure_compatible_schema()

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        assert conn.execute("SELECT role FROM dishes WHERE id='dish1'").fetchone() == ("main",)
        assert conn.execute(
            "SELECT qty FROM dish_ingredients WHERE dish_id='missing_dish' AND ingredient_id='ing1'"
        ).fetchone() == (50.0,)
        assert conn.execute(
            "INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json, allowed_weekdays_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("noodle1", "水餃", "noodle", "tw", None, "[]", "[1,2,3,4,5,6,7]"),
        ).rowcount == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == [("dish_ingredients", 2, "dishes", 1)]

def test_admin_write_routes_save_when_legacy_db_has_preexisting_fk_errors(tmp_path):
    db_path = tmp_path / "legacy_route_orphan.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
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
              PRIMARY KEY (dish_id, ingredient_id),
              FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
              FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT
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
            INSERT INTO ingredients(id, name, category, protein_group, default_unit)
            VALUES ('ing1', '雞肉', 'protein', NULL, 'g');
            INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json)
            VALUES ('dish1', '雞肉主菜', 'main', 'tw', 'chicken', '[]');
            INSERT INTO dish_ingredients(dish_id, ingredient_id, qty, unit)
            VALUES ('missing_dish', 'ing1', 50, 'g');
            """
        )

    ing_resp = admin_catalog.upsert_ingredient(
        "ing1",
        admin_catalog.IngredientUpsert(
            name="雞肉更新",
            category="protein",
            protein_group="chicken",
            default_unit="g",
        ),
        db_path=str(db_path),
    )
    dish_resp = admin_catalog.upsert_dish(
        "dish1",
        admin_catalog.DishUpsert(
            name="雞肉主菜更新",
            role="main",
            cuisine="tw",
            meat_type="chicken",
            tags=[],
            allowed_weekdays=[1, 2, 3],
            prep_minutes=15,
        ),
        db_path=str(db_path),
    )

    assert ing_resp == {"ok": True, "id": "ing1"}
    assert dish_resp == {"ok": True, "id": "dish1"}
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT name, protein_group FROM ingredients WHERE id='ing1'").fetchone() == ("雞肉更新", "chicken")
        assert conn.execute("SELECT name, prep_minutes FROM dishes WHERE id='dish1'").fetchone() == ("雞肉主菜更新", 15)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == [("dish_ingredients", 1, "dishes", 1)]
