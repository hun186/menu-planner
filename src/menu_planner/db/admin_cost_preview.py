from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Tuple


def fetch_latest_prices(conn: sqlite3.Connection, ingredient_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    if not ingredient_ids:
        return {}
    placeholders = ",".join(["?"] * len(ingredient_ids))
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


def fetch_ingredient_names(conn: sqlite3.Connection, ingredient_ids: List[str]) -> Dict[str, str]:
    if not ingredient_ids:
        return {}
    placeholders = ",".join(["?"] * len(ingredient_ids))
    rows = conn.execute(
        f"SELECT id, name FROM ingredients WHERE id IN ({placeholders})",
        ingredient_ids,
    ).fetchall()
    return {r[0]: r[1] for r in rows}


def fetch_dish_ingredients(
    conn: sqlite3.Connection,
    dish_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    where = ""
    params: List[Any] = []
    if dish_ids is not None:
        if not dish_ids:
            return []
        placeholders = ",".join(["?"] * len(dish_ids))
        where = f"WHERE dish_id IN ({placeholders})"
        params = list(dish_ids)

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


def build_cost_preview_rows(
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
