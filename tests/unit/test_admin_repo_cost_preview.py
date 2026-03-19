import sqlite3

from src.menu_planner.db.admin_repo import SQLiteAdminRepo


def _build_db(path: str):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE ingredients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            protein_group TEXT,
            default_unit TEXT NOT NULL
        );

        CREATE TABLE ingredient_prices (
            ingredient_id TEXT NOT NULL,
            price_date TEXT NOT NULL,
            price_per_unit REAL NOT NULL,
            unit TEXT NOT NULL,
            PRIMARY KEY (ingredient_id, price_date)
        );

        CREATE TABLE unit_conversions (
            from_unit TEXT NOT NULL,
            to_unit TEXT NOT NULL,
            factor REAL NOT NULL,
            PRIMARY KEY (from_unit, to_unit)
        );

        CREATE TABLE dish_ingredients (
            dish_id TEXT NOT NULL,
            ingredient_id TEXT NOT NULL,
            qty REAL NOT NULL,
            unit TEXT NOT NULL
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
    conn.executemany(
        "INSERT INTO ingredients(id, name, category, default_unit) VALUES(?, ?, ?, ?)",
        [
            ("ing-a", "白米", "穀物", "g"),
            ("ing-b", "胡蘿蔔", "蔬菜", "g"),
        ],
    )
    conn.executemany(
        "INSERT INTO ingredient_prices(ingredient_id, price_date, price_per_unit, unit) VALUES(?, ?, ?, ?)",
        [
            ("ing-a", "2026-03-01", 0.05, "g"),
            ("ing-a", "2026-03-15", 0.07, "g"),
            ("ing-b", "2026-03-10", 12, "kg"),
        ],
    )
    conn.execute("INSERT INTO unit_conversions(from_unit, to_unit, factor) VALUES(?, ?, ?)", ("g", "kg", 0.001))
    conn.executemany(
        "INSERT INTO dish_ingredients(dish_id, ingredient_id, qty, unit) VALUES(?, ?, ?, ?)",
        [
            ("dish-1", "ing-a", 100, "g"),
            ("dish-1", "ing-b", 200, "g"),
            ("dish-2", "ing-b", 1, "包"),
        ],
    )
    conn.commit()
    conn.close()


def test_preview_dish_cost_uses_latest_price_and_conversion(tmp_path):
    db_path = tmp_path / "menu.db"
    _build_db(str(db_path))
    repo = SQLiteAdminRepo(str(db_path))

    out = repo.preview_dish_cost(
        [
            {"ingredient_id": "ing-a", "qty": 100, "unit": "g"},
            {"ingredient_id": "ing-b", "qty": 200, "unit": "g"},
        ]
    )

    assert out["per_serving_cost"] == 9.4
    assert out["total_cost"] == 9.4
    assert out["warnings"] == []


def test_preview_dish_cost_reports_warnings(tmp_path):
    db_path = tmp_path / "menu.db"
    _build_db(str(db_path))
    repo = SQLiteAdminRepo(str(db_path))

    out = repo.preview_dish_cost(
        [
            {"ingredient_id": "ing-x", "qty": 1, "unit": "g"},
            {"ingredient_id": "ing-b", "qty": 3, "unit": "包"},
        ]
    )

    assert out["per_serving_cost"] == 0
    reasons = {x["reason"] for x in out["warnings"]}
    assert reasons == {"ingredient_not_found", "unit_mismatch"}


def test_list_dish_cost_preview_returns_cost_and_warning_count(tmp_path):
    db_path = tmp_path / "menu.db"
    _build_db(str(db_path))
    repo = SQLiteAdminRepo(str(db_path))

    out = repo.list_dish_cost_preview()
    by_id = {x["dish_id"]: x for x in out}

    assert by_id["dish-1"]["per_serving_cost"] == 9.4
    assert by_id["dish-1"]["warning_count"] == 0
    assert by_id["dish-2"]["per_serving_cost"] == 0
    assert by_id["dish-2"]["warning_count"] == 1


def test_get_inventory_handles_whitespace_mismatch_in_inventory_id(tmp_path):
    db_path = tmp_path / "menu.db"
    _build_db(str(db_path))
    repo = SQLiteAdminRepo(str(db_path))

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO ingredients(id, name, category, default_unit) VALUES(?, ?, ?, ?)",
            ("ing_芋圓", "芋圓", "starch", "斤"),
        )
        conn.execute(
            "INSERT INTO inventory(ingredient_id, qty_on_hand, unit, updated_at, expiry_date) VALUES(?, ?, ?, ?, ?)",
            ("ing_ 芋圓", 1, "斤", "2026-03-10", "2026-03-21"),
        )

    got = repo.get_inventory("ing_芋圓")
    assert got is not None
    assert got["qty_on_hand"] == 1.0
    assert got["unit"] == "斤"
