#src/menu_planner/db/admin_repo.py
from __future__ import annotations

import json
import sqlite3
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

class SQLiteAdminRepo:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    @staticmethod
    def _compact_identifier(value: str) -> str:
        return (
            str(value or "")
            .replace(" ", "")
            .replace("\t", "")
            .replace("　", "")
        )

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

    def merge_ingredient(self, source_ingredient_id: str, target_ingredient_id: str) -> Dict[str, Any]:
        source_id = str(source_ingredient_id or "").strip()
        target_id = str(target_ingredient_id or "").strip()
        if not source_id or not target_id:
            raise ValueError("source_ingredient_id / target_ingredient_id 不可為空")
        if source_id == target_id:
            raise ValueError("來源與目標食材不可相同")

        merged_dish_count = 0
        merged_price_count = 0
        merged_inventory = False

        with self._conn() as conn:
            src_exists = conn.execute("SELECT 1 FROM ingredients WHERE id=? LIMIT 1", (source_id,)).fetchone()
            tgt_exists = conn.execute("SELECT 1 FROM ingredients WHERE id=? LIMIT 1", (target_id,)).fetchone()
            if not src_exists:
                raise ValueError(f"找不到來源食材：{source_id}")
            if not tgt_exists:
                raise ValueError(f"找不到目標食材：{target_id}")

            conv_map = self._fetch_unit_conversions_conn(conn)

            source_rows = conn.execute(
                """
                SELECT dish_id, qty, unit
                FROM dish_ingredients
                WHERE ingredient_id=?
                ORDER BY dish_id
                """,
                (source_id,),
            ).fetchall()
            for dish_id, src_qty_raw, src_unit in source_rows:
                src_qty = float(src_qty_raw or 0)
                existing = conn.execute(
                    """
                    SELECT qty, unit
                    FROM dish_ingredients
                    WHERE dish_id=? AND ingredient_id=?
                    LIMIT 1
                    """,
                    (dish_id, target_id),
                ).fetchone()
                if not existing:
                    conn.execute(
                        """
                        UPDATE dish_ingredients
                        SET ingredient_id=?
                        WHERE dish_id=? AND ingredient_id=?
                        """,
                        (target_id, dish_id, source_id),
                    )
                    merged_dish_count += 1
                    continue

                tgt_qty = float(existing[0] or 0)
                tgt_unit = existing[1]
                converted_qty = self._convert_qty(src_qty, src_unit, tgt_unit, conv_map)
                if converted_qty is None:
                    raise ValueError(
                        f"菜色 {dish_id} 的食材單位無法合併：{source_id}({src_unit}) -> {target_id}({tgt_unit})"
                    )

                conn.execute(
                    """
                    UPDATE dish_ingredients
                    SET qty=?
                    WHERE dish_id=? AND ingredient_id=?
                    """,
                    (tgt_qty + converted_qty, dish_id, target_id),
                )
                conn.execute(
                    """
                    DELETE FROM dish_ingredients
                    WHERE dish_id=? AND ingredient_id=?
                    """,
                    (dish_id, source_id),
                )
                merged_dish_count += 1

            source_prices = conn.execute(
                """
                SELECT price_date, price_per_unit, unit
                FROM ingredient_prices
                WHERE ingredient_id=?
                ORDER BY price_date
                """,
                (source_id,),
            ).fetchall()
            for price_date, price_per_unit, unit in source_prices:
                exists = conn.execute(
                    """
                    SELECT 1
                    FROM ingredient_prices
                    WHERE ingredient_id=? AND price_date=?
                    LIMIT 1
                    """,
                    (target_id, price_date),
                ).fetchone()
                if exists:
                    continue
                conn.execute(
                    """
                    INSERT INTO ingredient_prices(ingredient_id, price_date, price_per_unit, unit)
                    VALUES (?, ?, ?, ?)
                    """,
                    (target_id, price_date, float(price_per_unit), unit),
                )
                merged_price_count += 1

            src_inv = conn.execute(
                """
                SELECT qty_on_hand, unit, updated_at, expiry_date
                FROM inventory
                WHERE ingredient_id=?
                LIMIT 1
                """,
                (source_id,),
            ).fetchone()
            tgt_inv = conn.execute(
                """
                SELECT qty_on_hand, unit, updated_at, expiry_date
                FROM inventory
                WHERE ingredient_id=?
                LIMIT 1
                """,
                (target_id,),
            ).fetchone()
            if src_inv and not tgt_inv:
                conn.execute("UPDATE inventory SET ingredient_id=? WHERE ingredient_id=?", (target_id, source_id))
                merged_inventory = True
            elif src_inv and tgt_inv:
                src_qty = float(src_inv[0] or 0)
                src_unit = src_inv[1]
                src_updated_at = src_inv[2]
                src_expiry = src_inv[3]

                tgt_qty = float(tgt_inv[0] or 0)
                tgt_unit = tgt_inv[1]
                tgt_updated_at = tgt_inv[2]
                tgt_expiry = tgt_inv[3]

                converted_qty = self._convert_qty(src_qty, src_unit, tgt_unit, conv_map)
                if converted_qty is None:
                    raise ValueError(f"庫存單位無法合併：{source_id}({src_unit}) -> {target_id}({tgt_unit})")

                merged_qty = tgt_qty + converted_qty
                merged_updated = max(src_updated_at or "", tgt_updated_at or "") or date.today().isoformat()
                merged_expiry = self._earliest_date(src_expiry, tgt_expiry)

                conn.execute(
                    """
                    UPDATE inventory
                    SET qty_on_hand=?, unit=?, updated_at=?, expiry_date=?
                    WHERE ingredient_id=?
                    """,
                    (merged_qty, tgt_unit, merged_updated, merged_expiry, target_id),
                )
                conn.execute("DELETE FROM inventory WHERE ingredient_id=?", (source_id,))
                merged_inventory = True

            deleted = conn.execute("DELETE FROM ingredients WHERE id=?", (source_id,)).rowcount
            if deleted <= 0:
                raise ValueError(f"刪除來源食材失敗：{source_id}")

        return {
            "source_ingredient_id": source_id,
            "target_ingredient_id": target_id,
            "merged_dish_count": merged_dish_count,
            "merged_price_count": merged_price_count,
            "merged_inventory": merged_inventory,
        }

    def ingredient_exists(self, ingredient_id: str) -> bool:
        with self._conn() as conn:
            r = conn.execute("SELECT 1 FROM ingredients WHERE id=? LIMIT 1", (ingredient_id,)).fetchone()
        return r is not None

    def list_ingredients(
        self,
        *,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        where_sql = ""
        params: List[Any] = []
        keyword = (q or "").strip()
        if keyword:
            where_sql = "WHERE LOWER(id) LIKE ? OR LOWER(name) LIKE ?"
            like = f"%{keyword.lower()}%"
            params.extend([like, like])

        limit = max(1, int(page_size))
        offset = (max(1, int(page)) - 1) * limit

        with self._conn() as conn:
            total = conn.execute(
                f"SELECT COUNT(1) FROM ingredients {where_sql}",
                params,
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT id, name, category, protein_group, default_unit
                FROM ingredients
                {where_sql}
                ORDER BY name, id
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()

        total = int(total or 0)
        total_pages = max(1, (total + limit - 1) // limit) if total else 1
        return {
            "items": [
                {
                    "id": r[0],
                    "name": r[1],
                    "category": r[2],
                    "protein_group": r[3],
                    "default_unit": r[4],
                }
                for r in rows
            ],
            "page": max(1, int(page)),
            "page_size": limit,
            "total": total,
            "total_pages": total_pages,
        }
    
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
        normalized_id = self._compact_identifier(ingredient_id)
        with self._conn() as conn:
            r = conn.execute("""
              SELECT qty_on_hand, unit, updated_at, expiry_date
              FROM inventory
              WHERE ingredient_id=?
            """, (ingredient_id,)).fetchone()
            if not r and normalized_id:
                r = conn.execute(
                    """
                    SELECT qty_on_hand, unit, updated_at, expiry_date
                    FROM inventory
                    WHERE REPLACE(REPLACE(REPLACE(ingredient_id, ' ', ''), CHAR(9), ''), '　', '')=?
                    LIMIT 1
                    """,
                    (normalized_id,),
                ).fetchone()
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

    def list_inventory_summary(
        self,
        *,
        q: Optional[str] = None,
        only_in_stock: bool = False,
    ) -> List[Dict[str, Any]]:
        keyword = (q or "").strip().lower()
        where_parts: List[str] = []
        params: List[Any] = []
        if keyword:
            where_parts.append("(LOWER(i.id) LIKE ? OR LOWER(i.name) LIKE ?)")
            like = f"%{keyword}%"
            params.extend([like, like])
        if only_in_stock:
            where_parts.append("COALESCE(inv.qty_on_hand, 0) > 0")
        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

        with self._conn() as conn:
            rows = conn.execute(
                f"""
                SELECT
                  i.id,
                  i.name,
                  i.category,
                  i.default_unit,
                  inv.qty_on_hand,
                  inv.unit,
                  inv.updated_at,
                  inv.expiry_date,
                  COALESCE(di_ref.ref_count, 0) AS dish_ref_count
                FROM ingredients i
                LEFT JOIN inventory inv ON inv.ingredient_id = i.id
                LEFT JOIN (
                  SELECT ingredient_id, COUNT(DISTINCT dish_id) AS ref_count
                  FROM dish_ingredients
                  GROUP BY ingredient_id
                ) di_ref ON di_ref.ingredient_id = i.id
                {where_sql}
                ORDER BY
                  CASE WHEN inv.expiry_date IS NULL OR inv.expiry_date = '' THEN 1 ELSE 0 END,
                  inv.expiry_date ASC,
                  i.name ASC,
                  i.id ASC
                """,
                params,
            ).fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            qty = None if r[4] is None else float(r[4])
            out.append(
                {
                    "ingredient_id": r[0],
                    "ingredient_name": r[1],
                    "category": r[2],
                    "default_unit": r[3],
                    "qty_on_hand": qty,
                    "inventory_unit": r[5],
                    "updated_at": r[6],
                    "expiry_date": r[7],
                    "dish_ref_count": int(r[8] or 0),
                }
            )
        return out
                
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

    def list_dishes(
        self,
        *,
        q: Optional[str] = None,
        role: Optional[str] = None,
        ingredient_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        where_parts: List[str] = []
        params: List[Any] = []
        join_sql = ""

        keyword = (q or "").strip()
        if keyword:
            where_parts.append("(LOWER(id) LIKE ? OR LOWER(name) LIKE ?)")
            like = f"%{keyword.lower()}%"
            params.extend([like, like])

        if role:
            where_parts.append("role = ?")
            params.append(role)

        ingredient_keyword = (ingredient_id or "").strip()
        if ingredient_keyword:
            join_sql = "JOIN dish_ingredients di ON di.dish_id = dishes.id"
            where_parts.append("di.ingredient_id = ?")
            params.append(ingredient_keyword)

        where_sql = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
        limit = max(1, int(page_size))
        offset = (max(1, int(page)) - 1) * limit

        with self._conn() as conn:
            total = conn.execute(
                f"SELECT COUNT(DISTINCT dishes.id) FROM dishes {join_sql} {where_sql}",
                params,
            ).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT DISTINCT dishes.id, dishes.name, dishes.role, dishes.cuisine, dishes.meat_type, dishes.tags_json
                FROM dishes
                {join_sql}
                {where_sql}
                ORDER BY dishes.role, dishes.name, dishes.id
                LIMIT ? OFFSET ?
                """,
                [*params, limit, offset],
            ).fetchall()

        total = int(total or 0)
        total_pages = max(1, (total + limit - 1) // limit) if total else 1
        return {
            "items": [
                {
                    "id": r[0],
                    "name": r[1],
                    "role": r[2],
                    "cuisine": r[3],
                    "meat_type": r[4],
                    "tags": self._safe_json_list(r[5]),
                }
                for r in rows
            ],
            "page": max(1, int(page)),
            "page_size": limit,
            "total": total,
            "total_pages": total_pages,
        }

    @staticmethod
    def _safe_json_list(raw: Optional[str]) -> List[Any]:
        try:
            data = json.loads(raw or "[]")
            return data if isinstance(data, list) else []
        except Exception:
            return []

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

    @staticmethod
    def _convert_qty(
        qty: float,
        source_unit: Optional[str],
        target_unit: Optional[str],
        conv_map: Dict[Tuple[str, str], float],
    ) -> Optional[float]:
        src = str(source_unit or "").strip()
        tgt = str(target_unit or "").strip()
        if src == tgt:
            return float(qty)
        if not src or not tgt:
            return None
        factor = conv_map.get((src, tgt))
        if factor is not None:
            return float(qty) * float(factor)
        inverse = conv_map.get((tgt, src))
        if inverse is not None and float(inverse) != 0:
            return float(qty) / float(inverse)
        return None

    @staticmethod
    def _earliest_date(d1: Optional[str], d2: Optional[str]) -> Optional[str]:
        candidates = [str(x).strip() for x in [d1, d2] if str(x or "").strip()]
        if not candidates:
            return None
        return min(candidates)

    def _fetch_unit_conversions_conn(self, conn: sqlite3.Connection) -> Dict[Tuple[str, str], float]:
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

    def list_dish_cost_preview(self, dish_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        rows = self._fetch_dish_ingredients(dish_ids=dish_ids)
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
