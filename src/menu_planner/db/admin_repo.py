#src/menu_planner/db/admin_repo.py
from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

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

    def price_exists(self, ingredient_id: str, price_date: str) -> bool:
        with self._conn() as conn:
            r = conn.execute(
                """
                SELECT 1
                FROM ingredient_prices
                WHERE ingredient_id=? AND price_date=?
                LIMIT 1
                """,
                (ingredient_id, price_date),
            ).fetchone()
        return r is not None
    
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

    def _fetch_unit_conversions(self) -> Dict[Tuple[str, str], float]:
        with self._conn() as conn:
            rows = conn.execute("SELECT from_unit, to_unit, factor FROM unit_conversions").fetchall()
        return {(r[0], r[1]): float(r[2]) for r in rows}

    def _fetch_latest_prices(self, ingredient_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not ingredient_ids:
            return {}
        placeholders = ",".join(["?"] * len(ingredient_ids))
        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT p.ingredient_id, p.price_date, p.price_per_unit, p.unit
                FROM ingredient_prices p
                JOIN (
                    SELECT ingredient_id, MAX(price_date) AS max_date
                    FROM ingredient_prices
                    WHERE ingredient_id IN ({placeholders})
                    GROUP BY ingredient_id
                ) t
                  ON t.ingredient_id = p.ingredient_id
                 AND t.max_date = p.price_date
                """,
                ingredient_ids,
            ).fetchall()
        return {
            r[0]: {
                "price_date": r[1],
                "price_per_unit": float(r[2]),
                "unit": r[3],
            }
            for r in rows
        }

    def _fetch_ingredient_names(self, ingredient_ids: List[str]) -> Dict[str, str]:
        if not ingredient_ids:
            return {}
        placeholders = ",".join(["?"] * len(ingredient_ids))
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT id, name FROM ingredients WHERE id IN ({placeholders})",
                ingredient_ids,
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def _fetch_dish_ingredients(self, dish_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        where = ""
        params: List[Any] = []
        if dish_ids is not None:
            if not dish_ids:
                return []
            placeholders = ",".join(["?"] * len(dish_ids))
            where = f"WHERE dish_id IN ({placeholders})"
            params = list(dish_ids)

        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT dish_id, ingredient_id, qty, unit
                FROM dish_ingredients
                {where}
                ORDER BY dish_id, ingredient_id
                """,
                params,
            ).fetchall()
        return [
            {
                "dish_id": r[0],
                "ingredient_id": r[1],
                "qty": float(r[2]),
                "unit": r[3],
            }
            for r in rows
        ]

    def _build_cost_preview_rows(
        self,
        items: List[Dict[str, Any]],
        ingredient_names: Dict[str, str],
        prices: Dict[str, Dict[str, Any]],
        conv: Dict[Tuple[str, str], float],
    ) -> Dict[str, Any]:
        total = 0.0
        rows: List[Dict[str, Any]] = []
        for x in items:
            ing_id = str(x.get("ingredient_id") or "")
            qty = float(x.get("qty") or 0)
            unit = str(x.get("unit") or "")
            row = {
                "ingredient_id": ing_id,
                "ingredient_name": ingredient_names.get(ing_id),
                "qty": qty,
                "unit": unit,
                "status": "ok",
                "reason": None,
                "price_date": None,
                "price_per_unit": None,
                "price_unit": None,
                "cost": 0.0,
            }
            if not ingredient_names.get(ing_id):
                row["status"] = "warning"
                row["reason"] = "ingredient_not_found"
                rows.append(row)
                continue

            p = prices.get(ing_id)
            if not p:
                row["status"] = "warning"
                row["reason"] = "missing_price"
                rows.append(row)
                continue

            price_unit = p["unit"]
            qty_in_price_unit = qty
            if unit != price_unit:
                factor = conv.get((unit, price_unit))
                if factor is None:
                    row["status"] = "warning"
                    row["reason"] = "unit_mismatch"
                    row["price_date"] = p["price_date"]
                    row["price_per_unit"] = p["price_per_unit"]
                    row["price_unit"] = price_unit
                    rows.append(row)
                    continue
                qty_in_price_unit = qty * factor

            cost = qty_in_price_unit * float(p["price_per_unit"])
            row["price_date"] = p["price_date"]
            row["price_per_unit"] = p["price_per_unit"]
            row["price_unit"] = price_unit
            row["cost"] = round(cost, 4)
            total += cost
            rows.append(row)

        per_serving = round(total, 2)
        warnings = [r for r in rows if r["status"] != "ok"]
        return {
            "per_serving_cost": per_serving,
            "rows": rows,
            "warnings": warnings,
        }

    def preview_dish_cost(self, items: List[Dict[str, Any]], servings: float = 1.0) -> Dict[str, Any]:
        ingredient_ids = [str(x["ingredient_id"]) for x in items if x.get("ingredient_id")]
        ingredient_names = self._fetch_ingredient_names(ingredient_ids)
        prices = self._fetch_latest_prices(ingredient_ids)
        conv = self._fetch_unit_conversions()

        preview = self._build_cost_preview_rows(items, ingredient_names, prices, conv)
        per_serving = preview["per_serving_cost"]
        return {
            "servings": servings,
            "per_serving_cost": per_serving,
            "total_cost": round(per_serving * servings, 2),
            "rows": preview["rows"],
            "warnings": preview["warnings"],
        }

    def list_dish_cost_preview(self) -> List[Dict[str, Any]]:
        rows = self._fetch_dish_ingredients(dish_ids=None)
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        ingredient_ids: List[str] = []
        for x in rows:
            dish_id = x["dish_id"]
            grouped.setdefault(dish_id, []).append({
                "ingredient_id": x["ingredient_id"],
                "qty": x["qty"],
                "unit": x["unit"],
            })
            ingredient_ids.append(x["ingredient_id"])

        ingredient_ids = sorted(set(ingredient_ids))
        ingredient_names = self._fetch_ingredient_names(ingredient_ids)
        prices = self._fetch_latest_prices(ingredient_ids)
        conv = self._fetch_unit_conversions()

        out: List[Dict[str, Any]] = []
        for dish_id, items in grouped.items():
            preview = self._build_cost_preview_rows(items, ingredient_names, prices, conv)
            out.append({
                "dish_id": dish_id,
                "per_serving_cost": preview["per_serving_cost"],
                "warning_count": len(preview["warnings"]),
                "warnings": preview["warnings"],
            })

        return out
