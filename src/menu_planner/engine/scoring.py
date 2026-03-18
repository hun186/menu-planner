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
    chosen: Dict[str, DishFeatures],  # keys: main/side1/side2/veg/soup/fruit
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
            chosen["veg"].inventory_hit_ratio
        ) * 0.5

        # 偏好食材（多選）：若當日菜色命中偏好食材，額外給一點 bonus。
        # 注意：這是 soft 偏好，不是 hard 排除；即使不在偏好清單，仍可能被排到。
        preferred_ids = {
            str(x).strip()
            for x in (context.get("inventory_prefer_ingredient_ids") or [])
            if str(x).strip()
        }
        if preferred_ids:
            dishes = [
                chosen["main"],
                chosen["soup"],
                chosen["side1"],
                chosen["side2"],
                chosen["veg"],
            ]
            prefer_hits = 0
            for d in dishes:
                used = set(d.used_inventory_ingredients or [])
                prefer_hits += len(used & preferred_ids)
            if prefer_hits > 0:
                # 比一般庫存命中弱一些，避免壓過成本/重複等目標。
                items["prefer_ingredient_bonus"] = inv_bonus * (prefer_hits * 0.35)

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
            one(chosen["veg"])
        )

    # ===== 重複懲罰（soft；讓 local_search/報表看得出差異）=====
    cur_main_id  = context.get("cur_main_id")
    cur_soup_id  = context.get("cur_soup_id")
    cur_fruit_id = context.get("cur_fruit_id")
    cur_side_ids = context.get("cur_side_ids") or []
    cur_veg_id   = context.get("cur_veg_id")
    
    recent_main_ids = context.get("recent_main_ids") or []
    recent_soups    = context.get("recent_soups") or []
    recent_fruits   = context.get("recent_fruits") or []
    recent_sides    = context.get("recent_sides") or []
    recent_vegs     = context.get("recent_vegs") or []
    
    w_main  = float(weights.get("repeat_penalty_main", 0))
    w_soup  = float(weights.get("repeat_penalty_soup", 0))
    w_side  = float(weights.get("repeat_penalty_side", 0))
    w_fruit = float(weights.get("repeat_penalty_fruit", 0))
    
    if w_main > 0 and cur_main_id:
        rep = recent_main_ids.count(cur_main_id)
        if rep > 0:
            items["repeat_penalty_main"] = w_main * rep
    
    if w_soup > 0 and cur_soup_id:
        rep = recent_soups.count(cur_soup_id)
        if rep > 0:
            items["repeat_penalty_soup"] = w_soup * rep
    
    if w_fruit > 0 and cur_fruit_id:
        rep = recent_fruits.count(cur_fruit_id)
        if rep > 0:
            items["repeat_penalty_fruit"] = w_fruit * rep
    
    if w_side > 0 and cur_side_ids:
        rep = sum(recent_sides.count(sid) for sid in cur_side_ids)
        if rep > 0:
            items["repeat_penalty_side"] = w_side * rep
    if w_side > 0 and cur_veg_id:
        rep = recent_vegs.count(cur_veg_id)
        if rep > 0:
            items["repeat_penalty_veg"] = w_side * rep
            
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
