#src/menu_planner/db/admin_repo.py
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional

class SQLiteAdminRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    # ---------- ingredients ----------
    def upsert_ingredient(self, ingredient_id: str, body: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute("""
              INSERT INTO ingredients(id, name, category, protein_group, default_unit)
              VALUES (?, ?, ?, ?, ?)
              ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                category=excluded.category,
                protein_group=excluded.protein_group,
                default_unit=excluded.default_unit
            """, (
                ingredient_id,
                body["name"],
                body["category"],
                body.get("protein_group"),
                body["default_unit"],
            ))

    def delete_ingredient(self, ingredient_id: str) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM ingredients WHERE id=?", (ingredient_id,))
            return cur.rowcount

    def ingredient_exists(self, ingredient_id: str) -> bool:
        with self._conn() as conn:
            r = conn.execute("SELECT 1 FROM ingredients WHERE id=? LIMIT 1", (ingredient_id,)).fetchone()
        return r is not None
    
    # ---------- prices ----------
    def list_prices(self, ingredient_id: str, limit: int = 30):
        with self._conn() as conn:
            rows = conn.execute("""
              SELECT price_date, price_per_unit, unit
              FROM ingredient_prices
              WHERE ingredient_id=?
              ORDER BY price_date DESC
              LIMIT ?
            """, (ingredient_id, limit)).fetchall()
        return [{"price_date": r[0], "price_per_unit": float(r[1]), "unit": r[2]} for r in rows]
    
    def upsert_price(self, ingredient_id: str, price_date: str, body):
        with self._conn() as conn:
            conn.execute("""
              INSERT INTO ingredient_prices(ingredient_id, price_date, price_per_unit, unit)
              VALUES (?, ?, ?, ?)
              ON CONFLICT(ingredient_id, price_date) DO UPDATE SET
                price_per_unit=excluded.price_per_unit,
                unit=excluded.unit
            """, (ingredient_id, price_date, float(body["price_per_unit"]), body["unit"]))
    
    def delete_price(self, ingredient_id: str, price_date: str) -> int:
        with self._conn() as conn:
            cur = conn.execute("""
              DELETE FROM ingredient_prices
              WHERE ingredient_id=? AND price_date=?
            """, (ingredient_id, price_date))
            return cur.rowcount
    
    # ---------- inventory ----------
    def get_inventory(self, ingredient_id: str):
        with self._conn() as conn:
            r = conn.execute("""
              SELECT qty_on_hand, unit, updated_at, expiry_date
              FROM inventory
              WHERE ingredient_id=?
            """, (ingredient_id,)).fetchone()
        if not r:
            return None
        return {
            "qty_on_hand": float(r[0]),
            "unit": r[1],
            "updated_at": r[2],
            "expiry_date": r[3],
        }
    
    def upsert_inventory(self, ingredient_id: str, body):
        with self._conn() as conn:
            conn.execute("""
              INSERT INTO inventory(ingredient_id, qty_on_hand, unit, updated_at, expiry_date)
              VALUES (?, ?, ?, ?, ?)
              ON CONFLICT(ingredient_id) DO UPDATE SET
                qty_on_hand=excluded.qty_on_hand,
                unit=excluded.unit,
                updated_at=excluded.updated_at,
                expiry_date=excluded.expiry_date
            """, (
                ingredient_id,
                float(body["qty_on_hand"]),
                body["unit"],
                body["updated_at"],
                body.get("expiry_date"),
            ))
                
    def find_dishes_using_ingredient(self, ingredient_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("""
              SELECT d.id, d.name, d.role
              FROM dish_ingredients di
              JOIN dishes d ON d.id = di.dish_id
              WHERE di.ingredient_id = ?
              ORDER BY d.role, d.name
            """, (ingredient_id,)).fetchall()
        return [{"id": r[0], "name": r[1], "role": r[2]} for r in rows]

    # ---------- dishes ----------
    def upsert_dish(self, dish_id: str, body: Dict[str, Any]) -> None:
        tags_json = json.dumps(body.get("tags", []), ensure_ascii=False)
        with self._conn() as conn:
            conn.execute("""
              INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json)
              VALUES (?, ?, ?, ?, ?, ?)
              ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                role=excluded.role,
                cuisine=excluded.cuisine,
                meat_type=excluded.meat_type,
                tags_json=excluded.tags_json
            """, (
                dish_id,
                body["name"],
                body["role"],
                body.get("cuisine"),
                body.get("meat_type"),
                tags_json,
            ))

    def delete_dish(self, dish_id: str) -> int:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM dishes WHERE id=?", (dish_id,))
            return cur.rowcount

    def dish_exists(self, dish_id: str) -> bool:
        with self._conn() as conn:
            r = conn.execute("SELECT 1 FROM dishes WHERE id=? LIMIT 1", (dish_id,)).fetchone()
        return r is not None

    # ---------- dish_ingredients ----------
    def get_dish_ingredients(self, dish_id: str) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute("""
              SELECT ingredient_id, qty, unit
              FROM dish_ingredients
              WHERE dish_id=?
              ORDER BY ingredient_id
            """, (dish_id,)).fetchall()
        return [{"ingredient_id": r[0], "qty": float(r[1]), "unit": r[2]} for r in rows]

    def replace_dish_ingredients(self, dish_id: str, items: List[Dict[str, Any]]) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM dish_ingredients WHERE dish_id=?", (dish_id,))
            if items:
                conn.executemany("""
                  INSERT INTO dish_ingredients(dish_id, ingredient_id, qty, unit)
                  VALUES (?, ?, ?, ?)
                """, [
                    (dish_id, x["ingredient_id"], float(x["qty"]), x["unit"])
                    for x in items
                ])

    def find_missing_ingredients(self, ids: List[str]) -> List[str]:
        if not ids:
            return []
        placeholders = ",".join(["?"] * len(ids))
        with self._conn() as conn:
            rows = conn.execute(f"SELECT id FROM ingredients WHERE id IN ({placeholders})", ids).fetchall()
        found = {r[0] for r in rows}
        return [x for x in ids if x not in found]

