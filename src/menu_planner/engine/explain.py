# src/menu_planner/engine/explain.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional

from ..db.repo import Dish
from .constraints import PlanDay
from .features import DishFeatures


def build_explanations(
    start_date: date,
    plan_days: List[PlanDay],
    dishes_by_id: Dict[str, Dish],
    feat: Dict[str, DishFeatures],
    day_scores: List[Dict],
) -> Dict:
    out_days: List[Dict] = []

    score_map = {d["day_index"]: d for d in day_scores}

    for i, d in enumerate(plan_days):
        dt = start_date + timedelta(days=i)

        def dish_info(did: str) -> Dict:
            di = dishes_by_id[did]
            f = feat[did]
            return {
                "id": did,
                "name": di.name,
                "role": di.role,
                "meat_type": di.meat_type,
                "cuisine": di.cuisine,
                "cost": f.cost_per_serving,
                "inventory_hit_ratio": f.inventory_hit_ratio,
                "near_expiry_days_min": f.near_expiry_days_min,
                "used_inventory_ingredients": f.used_inventory_ingredients,
            }

        day_cost = (
            feat[d.main].cost_per_serving
            + feat[d.soup].cost_per_serving
            + feat[d.fruit].cost_per_serving
            + sum(feat[s].cost_per_serving for s in d.sides)
        )

        sd = score_map.get(i, {})
        out_days.append({
            "date": dt.isoformat(),
            "day_index": i,
            "items": {
                "main": dish_info(d.main),
                "sides": [dish_info(x) for x in d.sides],
                "soup": dish_info(d.soup),
                "fruit": dish_info(d.fruit),
            },
            "day_cost": round(day_cost, 2),
            "score": sd.get("score"),
            "score_breakdown": sd.get("score_breakdown"),
        })

    total_score = sum((d.get("score") or 0) for d in score_map.values())
    total_cost = sum(d["day_cost"] for d in out_days)

    return {
        "summary": {
            "days": len(plan_days),
            "total_cost": round(total_cost, 2),
            "avg_cost_per_day": round(total_cost / max(len(plan_days), 1), 2),
            "total_score": round(total_score, 2),
        },
        "days": out_days
    }
