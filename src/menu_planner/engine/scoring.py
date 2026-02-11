# src/menu_planner/engine/scoring.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple

from .features import DishFeatures


@dataclass
class ScoreBreakdown:
    total: float
    items: Dict[str, float]   # 正=扣分，負=加分
    penalty_total: float = 0.0
    bonus_total: float = 0.0
    fitness: float = 0.0      # = -total（越高越好）



def score_day(
    day_cost: float,
    hard: Dict,
    weights: Dict,
    chosen: Dict[str, DishFeatures],  # keys: main/side1/side2/side3/soup/fruit
    context: Dict,
) -> ScoreBreakdown:
    items: Dict[str, float] = {}
    total = 0.0

    # 成本：超過 max 扣分、低於 min 也可扣分（讓它不要太偏）
    cr = hard.get("cost_range_per_person_per_day") or {}
    minv = cr.get("min")
    maxv = cr.get("max")
    if maxv is not None and day_cost > float(maxv):
        items["cost_over_max"] = (day_cost - float(maxv)) * float(weights.get("cost_over_max_penalty", 0))
    if minv is not None and day_cost < float(minv):
        items["cost_under_min"] = (float(minv) - day_cost) * float(weights.get("cost_under_min_penalty", 0))

    # 連續同肉（如果不是 hard 禁止，就當 soft 扣分）
    prev_meat = context.get("prev_main_meat")
    cur_meat = chosen["main"].meat_type
    if prev_meat is not None and cur_meat is not None and prev_meat == cur_meat:
        items["consecutive_same_meat"] = float(weights.get("consecutive_same_meat_penalty", 0))

    # 連續同菜系（soft）
    prev_cuisine = context.get("prev_main_cuisine")
    cur_cuisine = chosen["main"].cuisine
    if prev_cuisine and cur_cuisine and prev_cuisine == cur_cuisine:
        items["cuisine_consecutive"] = float(weights.get("cuisine_consecutive_penalty", 0))

    # 庫存 / 近到期：加分（用負數代表 bonus）
    if context.get("prefer_use_inventory", False):
        inv_bonus = float(weights.get("use_inventory_bonus", 0))
        # 用到庫存比例越高，加分越多
        hit = chosen["main"].inventory_hit_ratio
        items["use_inventory_bonus_main"] = inv_bonus * hit  # inv_bonus 本身應該是負數
        # side/soup 也加一點
        items["use_inventory_bonus_others"] = inv_bonus * (
            chosen["soup"].inventory_hit_ratio +
            chosen["side1"].inventory_hit_ratio +
            chosen["side2"].inventory_hit_ratio +
            chosen["side3"].inventory_hit_ratio
        ) * 0.5

    if context.get("prefer_near_expiry", False):
        near_bonus = float(weights.get("near_expiry_bonus", 0))  # 預期是負數
        # 越接近到期（days 越小）加分越多；<0 代表過期，仍加分但你也可改成 hard 禁止
        def one(d: DishFeatures) -> float:
            if d.near_expiry_days_min is None:
                return 0.0
            days = d.near_expiry_days_min
            if days <= 0:
                return 1.0
            if days <= 2:
                return 0.8
            if days <= 4:
                return 0.5
            if days <= 7:
                return 0.2
            return 0.0

        items["near_expiry_bonus"] = near_bonus * (
            one(chosen["main"]) +
            one(chosen["soup"]) +
            one(chosen["side1"]) +
            one(chosen["side2"]) +
            one(chosen["side3"])
        )

    for k, v in items.items():
        total += float(v)

    penalty_total = sum(v for v in items.values() if v > 0)
    bonus_total = sum(-v for v in items.values() if v < 0)
    total = round(total, 2)

    return ScoreBreakdown(
        total=total,
        items={k: round(v, 2) for k, v in items.items()},
        penalty_total=round(penalty_total, 2),
        bonus_total=round(bonus_total, 2),
        fitness=round(-total, 2),
    )

