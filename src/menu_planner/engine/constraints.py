# src/menu_planner/engine/constraints.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from datetime import date


@dataclass
class PlanDay:
    main: str
    sides: List[str]
    soup: str
    fruit: str


def _week_index(day_idx: int) -> int:
    return day_idx // 7


def _window_start(day_idx: int, window: int) -> int:
    return max(0, day_idx - window + 1)

def _iter_prev_active_indices(day_idx: int, plan_days: List[PlanDay], window_active_days: int):
    """往回找最近 window_active_days 個『有排餐日』的索引（略過 offday）"""
    seen = 0
    for i in range(day_idx - 1, -1, -1):
        if i >= len(plan_days):
            continue
        if not plan_days[i].main:  # main=="" 視為 offday
            continue
        yield i
        seen += 1
        if seen >= window_active_days:
            break
        
def check_main_hard(
    day_idx: int,
    main_id: str,
    main_meat_type: Optional[str],
    plan_main_ids: List[str],
    plan_main_meats: List[Optional[str]],
    weekly_meat_counts: Dict[int, Dict[str, int]],
    hard: Dict,
    week_key: Optional[int] = None,   # ✅ 新增：由外部傳入真實週
) -> bool:
    allowed = set(hard.get("allowed_main_meat_types", []))
    if allowed and (main_meat_type not in allowed):
        return False

    if hard.get("no_consecutive_same_main_meat", False):
        if day_idx > 0 and plan_main_meats and plan_main_meats[-1] == main_meat_type:
            return False

    weekly_max = hard.get("weekly_max_main_meat", {}) or {}
    w = week_key if week_key is not None else (day_idx // 7)

    # ✅ 不要用 setdefault，避免在「檢查」時污染 state
    counts = weekly_meat_counts.get(w, {})
    if main_meat_type:
        max_allowed = weekly_max.get(main_meat_type)
        if max_allowed is not None:
            if counts.get(main_meat_type, 0) + 1 > int(max_allowed):
                return False

    rep = hard.get("repeat_limits", {}) or {}
    max_same_main = rep.get("max_same_main_in_30_days")
    if max_same_main is not None:
        if plan_main_ids.count(main_id) + 1 > int(max_same_main):
            return False

    if main_id in set(hard.get("exclude_dish_ids", []) or []):
        return False

    return True


def check_side_window_repeat(
    day_idx: int,
    side_ids_today: List[str],
    plan_days: List[PlanDay],
    max_repeat_in_7: int,
) -> bool:
    # ✅ 改成：最近 7 個「有排餐日」內，同一道 side 出現次數 <= max_repeat_in_7
    window_active_days = 7

    counts: Dict[str, int] = {}
    for i in _iter_prev_active_indices(day_idx, plan_days, window_active_days):
        for s in plan_days[i].sides or []:
            counts[s] = counts.get(s, 0) + 1

    for s in side_ids_today:
        if counts.get(s, 0) + 1 > max_repeat_in_7:
            return False
    return True

def check_soup_window_repeat(
    day_idx: int,
    soup_id_today: str,
    plan_days: List[PlanDay],
    max_repeat_in_7: int,
) -> bool:
    # ✅ 改成：最近 7 個「有排餐日」內，同一道 soup 出現次數 <= max_repeat_in_7
    window_active_days = 7

    cnt = 0
    for i in _iter_prev_active_indices(day_idx, plan_days, window_active_days):
        if plan_days[i].soup == soup_id_today:
            cnt += 1
            if cnt + 1 > max_repeat_in_7:
                return False
    return True

def check_fruit_window_repeat(
    day_idx: int,
    fruit_id_today: str,
    plan_days: List[PlanDay],
    max_repeat_in_7: int,
) -> bool:
    window_active_days = 7

    cnt = 0
    for i in _iter_prev_active_indices(day_idx, plan_days, window_active_days):
        if plan_days[i].fruit == fruit_id_today:
            cnt += 1
            if cnt + 1 > max_repeat_in_7:
                return False
    return True

def check_cost_range(
    total_cost: float,
    hard: Dict
) -> bool:
    cr = hard.get("cost_range_per_person_per_day")
    if not cr:
        return True
    minv = cr.get("min")
    maxv = cr.get("max")
    if minv is not None and total_cost < float(minv):
        return False
    if maxv is not None and total_cost > float(maxv):
        return False
    return True
