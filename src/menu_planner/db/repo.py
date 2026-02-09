# src/menu_planner/db/repo.py
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any


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
    role: str           # main/side/soup/fruit
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
            rows = conn.execute(
                "SELECT id, name, category, protein_group, default_unit FROM ingredients"
            ).fetchall()
        out: Dict[str, Ingredient] = {}
        for r in rows:
            out[r["id"]] = Ingredient(
                id=r["id"],
                name=r["name"],
                category=r["category"],
                protein_group=r["protein_group"],
                default_unit=r["default_unit"],
            )
        return out

    def fetch_dishes(self, role: Optional[str] = None) -> List[Dish]:
        sql = "SELECT id, name, role, cuisine, meat_type, tags_json FROM dishes"
        params: List[Any] = []
        if role:
            sql += " WHERE role = ?"
            params.append(role)
        sql += " ORDER BY role, name"

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        import json
        out: List[Dish] = []
        for r in rows:
            tags = []
            try:
                tags = json.loads(r["tags_json"] or "[]")
            except Exception:
                tags = []
            out.append(
                Dish(
                    id=r["id"],
                    name=r["name"],
                    role=r["role"],
                    cuisine=r["cuisine"],
                    meat_type=r["meat_type"],
                    tags=tags,
                )
            )
        return out

    def fetch_dish_ingredients(self, dish_ids: Optional[List[str]] = None) -> List[DishIngredient]:
        sql = "SELECT dish_id, ingredient_id, qty, unit FROM dish_ingredients"
        params: List[Any] = []
        if dish_ids:
            placeholders = ",".join(["?"] * len(dish_ids))
            sql += f" WHERE dish_id IN ({placeholders})"
            params.extend(dish_ids)

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return [
            DishIngredient(
                dish_id=r["dish_id"],
                ingredient_id=r["ingredient_id"],
                qty=float(r["qty"]),
                unit=r["unit"],
            )
            for r in rows
        ]

    def fetch_inventory(self) -> Dict[str, InventoryItem]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT ingredient_id, qty_on_hand, unit, updated_at, expiry_date FROM inventory"
            ).fetchall()
        out: Dict[str, InventoryItem] = {}
        for r in rows:
            out[r["ingredient_id"]] = InventoryItem(
                ingredient_id=r["ingredient_id"],
                qty_on_hand=float(r["qty_on_hand"]),
                unit=r["unit"],
                updated_at=r["updated_at"],
                expiry_date=r["expiry_date"],
            )
        return out

    def fetch_unit_conversions(self) -> Dict[Tuple[str, str], float]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT from_unit, to_unit, factor FROM unit_conversions"
            ).fetchall()
        return {(r["from_unit"], r["to_unit"]): float(r["factor"]) for r in rows}

    # ---------- prices ----------
    def fetch_latest_prices(self, price_date: Optional[str] = None) -> Dict[str, PriceItem]:
        """
        回傳每個 ingredient 的「最新一筆」價格。
        若指定 price_date：取 price_date 之前(含)的最新一筆；若沒有就取全表最新一筆。
        """
        with self.connect() as conn:
            if price_date:
                sql = """
                SELECT p.ingredient_id, p.price_date, p.price_per_unit, p.unit
                FROM ingredient_prices p
                JOIN (
                    SELECT ingredient_id, MAX(price_date) AS max_date
                    FROM ingredient_prices
                    WHERE price_date <= ?
                    GROUP BY ingredient_id
                ) x ON p.ingredient_id = x.ingredient_id AND p.price_date = x.max_date
                """
                rows = conn.execute(sql, [price_date]).fetchall()
            else:
                sql = """
                SELECT p.ingredient_id, p.price_date, p.price_per_unit, p.unit
                FROM ingredient_prices p
                JOIN (
                    SELECT ingredient_id, MAX(price_date) AS max_date
                    FROM ingredient_prices
                    GROUP BY ingredient_id
                ) x ON p.ingredient_id = x.ingredient_id AND p.price_date = x.max_date
                """
                rows = conn.execute(sql).fetchall()

        out: Dict[str, PriceItem] = {}
        for r in rows:
            out[r["ingredient_id"]] = PriceItem(
                ingredient_id=r["ingredient_id"],
                price_date=r["price_date"],
                price_per_unit=float(r["price_per_unit"]),
                unit=r["unit"],
            )
        return out
