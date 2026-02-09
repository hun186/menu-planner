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


def check_main_hard(
    day_idx: int,
    main_id: str,
    main_meat_type: Optional[str],
    plan_main_ids: List[str],
    plan_main_meats: List[Optional[str]],
    weekly_meat_counts: Dict[int, Dict[str, int]],
    hard: Dict,
) -> bool:
    allowed = set(hard.get("allowed_main_meat_types", []))
    if allowed and (main_meat_type not in allowed):
        return False

    if hard.get("no_consecutive_same_main_meat", False):
        if day_idx > 0 and plan_main_meats and plan_main_meats[-1] == main_meat_type:
            return False

    # weekly max
    weekly_max = hard.get("weekly_max_main_meat", {}) or {}
    w = _week_index(day_idx)
    counts = weekly_meat_counts.setdefault(w, {})
    if main_meat_type:
        max_allowed = weekly_max.get(main_meat_type)
        if max_allowed is not None:
            if counts.get(main_meat_type, 0) + 1 > int(max_allowed):
                return False

    # repeat limits (main in horizon)
    rep = hard.get("repeat_limits", {}) or {}
    max_same_main = rep.get("max_same_main_in_30_days")
    if max_same_main is not None:
        if plan_main_ids.count(main_id) + 1 > int(max_same_main):
            return False

    # include/exclude
    if main_id in set(hard.get("exclude_dish_ids", []) or []):
        return False

    return True


def check_side_window_repeat(
    day_idx: int,
    side_ids_today: List[str],
    plan_days: List[PlanDay],
    max_repeat_in_7: int,
) -> bool:
    # 限制：近 7 天內，同一道 side 出現次數 <= max_repeat_in_7
    start = _window_start(day_idx, 7)
    window_days = plan_days[start:day_idx]  # past only
    counts: Dict[str, int] = {}
    for d in window_days:
        for s in d.sides:
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
    start = _window_start(day_idx, 7)
    window_days = plan_days[start:day_idx]
    cnt = sum(1 for d in window_days if d.soup == soup_id_today)
    return (cnt + 1) <= max_repeat_in_7


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
