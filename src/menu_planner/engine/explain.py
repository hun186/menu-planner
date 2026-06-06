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
    active_mask: Optional[List[bool]] = None,
    role_counts_by_day: Optional[List[Dict[str, int]]] = None,
) -> Dict:
    out_days: List[Dict] = []

    # day_scores 可能有缺 day_index 的資料，保守寫法
    score_map = {d.get("day_index"): d for d in (day_scores or []) if d.get("day_index") is not None}

    def empty_dish(did: str = "") -> Dict:
        return {
            "id": did or "",
            "name": "",
            "role": "",
            "meat_type": None,
            "cuisine": None,
            "cost": 0.0,
            "inventory_hit_ratio": 0.0,
            "near_expiry_days_min": None,
            "used_inventory_ingredients": [],
        }

    def dish_info(did: str) -> Dict:
        # ✅ 空值 / 缺資料都不要炸
        if not did:
            return empty_dish("")
        if did not in dishes_by_id or did not in feat:
            return empty_dish(did)

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

    total_raw = 0.0
    total_fitness = 0.0
    total_cost = 0.0

    for i, d in enumerate(plan_days):
        dt = start_date + timedelta(days=i)
        sd = score_map.get(i, {}) or {}
        is_scheduled = True if active_mask is None else bool(active_mask[i])

        # ✅ 成本：優先用 fill_days_after_mains() 提供的 cost（尤其失敗日/超出範圍日）
        if sd.get("cost") is not None:
            day_cost = float(sd["cost"])
        else:
            day_cost = 0.0
            all_ids = (
                list(getattr(d, "mains", None) or ([d.main] if d.main else []))
                + list(getattr(d, "noodles", None) or ([d.noodle] if getattr(d, "noodle", "") else []))
                + list(d.sides or [])
                + list(getattr(d, "vegs", None) or ([d.veg] if d.veg else []))
                + list(getattr(d, "soups", None) or ([d.soup] if d.soup else []))
                + list(getattr(d, "fruits", None) or ([d.fruit] if d.fruit else []))
            )
            day_cost += sum(feat[x].cost_per_serving for x in all_ids if x and x in feat)

        day_cost = round(day_cost, 2)

        # ✅ sides 可能 None
        mains_list = [x for x in (getattr(d, "mains", None) or ([d.main] if d.main else [])) if x]
        noodles_list = [x for x in (getattr(d, "noodles", None) or ([d.noodle] if getattr(d, "noodle", "") else [])) if x]
        sides_list = [x for x in (d.sides or []) if x]
        vegs_list = [x for x in (getattr(d, "vegs", None) or ([d.veg] if d.veg else [])) if x]
        soups_list = [x for x in (getattr(d, "soups", None) or ([d.soup] if d.soup else [])) if x]
        fruits_list = [x for x in (getattr(d, "fruits", None) or ([d.fruit] if d.fruit else [])) if x]

        raw = sd.get("score")
        fitness = sd.get("score_fitness")

        out_days.append({
            "date": dt.isoformat(),
            "day_index": i,
            "is_scheduled": is_scheduled,

            # 失敗資訊透傳
            "failed": bool(sd.get("failed", False)),
            "reason_code": sd.get("reason_code"),
            "message": sd.get("message"),
            "details": sd.get("details"),

            "items": {
                "main": dish_info(d.main),
                "mains": [dish_info(x) for x in mains_list],
                "noodle": dish_info(getattr(d, "noodle", "")),
                "noodles": [dish_info(x) for x in noodles_list],
                "sides": [dish_info(x) for x in sides_list],
                "veg": dish_info(d.veg),
                "vegs": [dish_info(x) for x in vegs_list],
                "soup": dish_info(d.soup),
                "soups": [dish_info(x) for x in soups_list],
                "fruit": dish_info(d.fruit),
                "fruits": [dish_info(x) for x in fruits_list],
            },
            "day_cost": day_cost,

            # 原始分數（可能為負）
            "score": raw,
            "score_breakdown": sd.get("score_breakdown"),

            # ✅ 你新增的欄位
            "score_bonus_total": sd.get("score_bonus_total"),
            "score_penalty_total": sd.get("score_penalty_total"),
            "score_fitness": fitness,
            "score_summary": sd.get("score_summary"),
            "role_counts": (role_counts_by_day[i] if role_counts_by_day and i < len(role_counts_by_day) else None),
        })

        total_cost += day_cost
        if isinstance(raw, (int, float)):
            total_raw += float(raw)
        if isinstance(fitness, (int, float)):
            total_fitness += float(fitness)

    return {
        "summary": {
            "days": len(plan_days),
            "total_cost": round(total_cost, 2),
            "avg_cost_per_day": round(total_cost / max(len(plan_days), 1), 2),

            # 原本的總分（raw，可能是負）
            "total_score": round(total_raw, 2),

            # ✅ 新增：總目標匹配度（正向）
            "total_fitness": round(total_fitness, 2),

            # ✅ 你加的說明（保留）
            "score_legend": {
                "rule": "原始分數越低（越負）代表越符合偏好；正分代表違反偏好或成本懲罰。",
                "components": {
                    "bonus": "加分項（以負數表示，例如用到庫存、接近到期）",
                    "penalty": "扣分項（以正數表示，例如超出成本、連續同肉/同菜系）",
                    "fitness": "目標匹配度＝-原始分數（越高越好）"
                }
            }
        },
        "days": out_days
    }
