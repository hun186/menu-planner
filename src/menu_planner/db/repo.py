# src/menu_planner/db/repo.py
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple, Any


SQL_FETCH_INGREDIENTS = """
SELECT id, name, category, protein_group, default_unit
FROM ingredients
"""

SQL_FETCH_DISHES_BASE = """
SELECT id, name, role, cuisine, meat_type, tags_json
FROM dishes
"""

SQL_FETCH_DISH_INGREDIENTS_BASE = """
SELECT dish_id, ingredient_id, qty, unit
FROM dish_ingredients
"""

SQL_FETCH_INVENTORY = """
SELECT ingredient_id, qty_on_hand, unit, updated_at, expiry_date
FROM inventory
"""

SQL_FETCH_UNIT_CONVERSIONS = """
SELECT from_unit, to_unit, factor
FROM unit_conversions
"""

# Index note: keep `(ingredient_id, price_date)` indexed to avoid regressions as
# ingredient_prices grows and latest-price lookups become more expensive.
SQL_FETCH_LATEST_PRICES_WITH_CUTOFF = """
SELECT p.ingredient_id, p.price_date, p.price_per_unit, p.unit
FROM ingredient_prices p
JOIN (
    SELECT ingredient_id, MAX(price_date) AS max_date
    FROM ingredient_prices
    WHERE price_date <= ?
    GROUP BY ingredient_id
) x ON p.ingredient_id = x.ingredient_id AND p.price_date = x.max_date
"""

SQL_FETCH_LATEST_PRICES = """
SELECT p.ingredient_id, p.price_date, p.price_per_unit, p.unit
FROM ingredient_prices p
JOIN (
    SELECT ingredient_id, MAX(price_date) AS max_date
    FROM ingredient_prices
    GROUP BY ingredient_id
) x ON p.ingredient_id = x.ingredient_id AND p.price_date = x.max_date
"""


@dataclass(frozen=True)
class Ingredient:
    id: str
    name: str
    category: str
    protein_group: Optional[str]
    default_unit: str


@dataclass(frozen=True)
class Dish:
    id: str
    name: str
    role: str           # main/side/veg/soup/fruit
    cuisine: Optional[str]
    meat_type: Optional[str]
    tags: List[str]


@dataclass(frozen=True)
class DishIngredient:
    dish_id: str
    ingredient_id: str
    qty: float
    unit: str


@dataclass(frozen=True)
class InventoryItem:
    ingredient_id: str
    qty_on_hand: float
    unit: str
    updated_at: str
    expiry_date: Optional[str]


@dataclass(frozen=True)
class PriceItem:
    ingredient_id: str
    price_date: str
    price_per_unit: float
    unit: str


def _parse_json_list(raw_json: Optional[str]) -> List[str]:
    try:
        return json.loads(raw_json or "[]")
    except Exception:
        return []


def _map_ingredient(r: sqlite3.Row) -> Ingredient:
    return Ingredient(
        id=r["id"],
        name=r["name"],
        category=r["category"],
        protein_group=r["protein_group"],
        default_unit=r["default_unit"],
    )


def _map_dish(r: sqlite3.Row) -> Dish:
    return Dish(
        id=r["id"],
        name=r["name"],
        role=r["role"],
        cuisine=r["cuisine"],
        meat_type=r["meat_type"],
        tags=_parse_json_list(r["tags_json"]),
    )


def _map_dish_ingredient(r: sqlite3.Row) -> DishIngredient:
    return DishIngredient(
        dish_id=r["dish_id"],
        ingredient_id=r["ingredient_id"],
        qty=float(r["qty"]),
        unit=r["unit"],
    )


def _map_inventory_item(r: sqlite3.Row) -> InventoryItem:
    return InventoryItem(
        ingredient_id=r["ingredient_id"],
        qty_on_hand=float(r["qty_on_hand"]),
        unit=r["unit"],
        updated_at=r["updated_at"],
        expiry_date=r["expiry_date"],
    )


def _map_price_item(r: sqlite3.Row) -> PriceItem:
    return PriceItem(
        ingredient_id=r["ingredient_id"],
        price_date=r["price_date"],
        price_per_unit=float(r["price_per_unit"]),
        unit=r["unit"],
    )


class SQLiteRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # ---------- basic fetch ----------
    def fetch_ingredients(self) -> Dict[str, Ingredient]:
        with self.connect() as conn:
            rows = conn.execute(SQL_FETCH_INGREDIENTS).fetchall()
        return {r["id"]: _map_ingredient(r) for r in rows}

    def fetch_dishes(self, role: Optional[str] = None) -> List[Dish]:
        sql = SQL_FETCH_DISHES_BASE
        params: List[Any] = []
        if role:
            sql += " WHERE role = ?"
            params.append(role)
        sql += " ORDER BY role, name"

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [_map_dish(r) for r in rows]

    def fetch_dish_ingredients(self, dish_ids: Optional[List[str]] = None) -> List[DishIngredient]:
        sql = SQL_FETCH_DISH_INGREDIENTS_BASE
        params: List[Any] = []
        if dish_ids:
            placeholders = ",".join(["?"] * len(dish_ids))
            sql += f" WHERE dish_id IN ({placeholders})"
            params.extend(dish_ids)

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [_map_dish_ingredient(r) for r in rows]

    def fetch_inventory(self) -> Dict[str, InventoryItem]:
        with self.connect() as conn:
            rows = conn.execute(SQL_FETCH_INVENTORY).fetchall()
        return {r["ingredient_id"]: _map_inventory_item(r) for r in rows}

    def fetch_unit_conversions(self) -> Dict[Tuple[str, str], float]:
        with self.connect() as conn:
            rows = conn.execute(SQL_FETCH_UNIT_CONVERSIONS).fetchall()
        return {(r["from_unit"], r["to_unit"]): float(r["factor"]) for r in rows}

    # ---------- prices ----------
    def fetch_latest_prices(self, price_date: Optional[str] = None) -> Dict[str, PriceItem]:
        """
        回傳每個 ingredient 的「最新一筆」價格。
        若指定 price_date：取 price_date 之前(含)的最新一筆；若沒有就取全表最新一筆。
        """
        with self.connect() as conn:
            if price_date:
                rows = conn.execute(SQL_FETCH_LATEST_PRICES_WITH_CUTOFF, [price_date]).fetchall()
            else:
                rows = conn.execute(SQL_FETCH_LATEST_PRICES).fetchall()

        return {r["ingredient_id"]: _map_price_item(r) for r in rows}

    def fetch_catalog_summary(self) -> Dict[str, Any]:
        """
        彙整右欄可顯示的資料庫資訊：
        - 各角色菜色數量
        - 各角色涵蓋食材（distinct ingredient）數量
        - 有效庫存（未過期）筆數、食材數與總量
        """
        today = date.today().isoformat()
        with self.connect() as conn:
            dish_rows = conn.execute(
                """
                SELECT role, COUNT(*) AS dish_count
                FROM dishes
                GROUP BY role
                """
            ).fetchall()

            ingredient_rows = conn.execute(
                """
                SELECT d.role AS role, COUNT(DISTINCT di.ingredient_id) AS ingredient_count
                FROM dishes d
                LEFT JOIN dish_ingredients di ON di.dish_id = d.id
                GROUP BY d.role
                """
            ).fetchall()

            inventory_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS row_count,
                    COUNT(DISTINCT ingredient_id) AS ingredient_count,
                    COALESCE(SUM(qty_on_hand), 0) AS qty_sum
                FROM inventory
                WHERE qty_on_hand > 0
                  AND (expiry_date IS NULL OR date(expiry_date) >= date(?))
                """,
                [today],
            ).fetchone()

        roles = ["main", "side", "veg", "soup", "fruit"]
        dish_count_by_role = {role: 0 for role in roles}
        ingredient_count_by_role = {role: 0 for role in roles}

        for r in dish_rows:
            role = r["role"]
            if role in dish_count_by_role:
                dish_count_by_role[role] = int(r["dish_count"] or 0)

        for r in ingredient_rows:
            role = r["role"]
            if role in ingredient_count_by_role:
                ingredient_count_by_role[role] = int(r["ingredient_count"] or 0)

        return {
            "today": today,
            "dish_count_by_role": dish_count_by_role,
            "ingredient_count_by_role": ingredient_count_by_role,
            "inventory": {
                "valid_row_count": int(inventory_row["row_count"] or 0),
                "valid_ingredient_count": int(inventory_row["ingredient_count"] or 0),
                "valid_qty_sum": float(inventory_row["qty_sum"] or 0),
            },
        }
