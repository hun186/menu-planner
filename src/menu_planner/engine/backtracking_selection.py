from __future__ import annotations

import random
from typing import Dict, List, Optional, Set

from ..db.repo import Dish
from .constraints import (
    PlanDay,
    check_fruit_window_repeat,
    check_ingredient_window_repeat,
    check_side_window_repeat,
    check_soup_window_repeat,
    check_veg_window_repeat,
)
from .errors import PlanError
from .features import DishFeatures


def _repeat_limits(hard: Dict) -> Dict:
    return hard.get("repeat_limits", {}) or {}


def _ingredient_guardrails(hard: Dict) -> tuple[int, int, Optional[int], Set[str]]:
    rep = _repeat_limits(hard)
    max_ing_limit = int(
        rep.get("max_same_ingredient_in_window_days", rep.get("max_same_ingredient_in_7_days", 10**9))
    )
    ing_window_days = int(rep.get("ingredient_repeat_window_days", 4))
    max_ing_consec = rep.get("max_consecutive_ingredient_days")
    no_same_within_day = {
        str(x).strip()
        for x in (hard.get("no_same_ingredient_family_within_day") or [])
        if str(x).strip()
    }
    return max_ing_limit, ing_window_days, max_ing_consec, no_same_within_day


def pick_fruit(
    fruits: List[Dish],
    day_idx: int,
    plan_days: List[PlanDay],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    dish_ingredient_ids: Optional[Dict[str, Set[str]]] = None,
    selected_dish_ids: Optional[List[str]] = None,
) -> str:
    rep = _repeat_limits(hard)
    max_fruit_7 = int(rep.get("max_same_fruit_in_7_days", 10**9))
    max_ing_limit, ing_window_days, max_ing_consec, no_same_within_day = _ingredient_guardrails(hard)

    fruit_ids = [d.id for d in fruits if d.id in feat]
    if not fruit_ids:
        raise PlanError(code="FRUIT_EMPTY", message="找不到水果菜色。")

    for fid in fruit_ids:
        if dish_ingredient_ids is not None:
            base = list(selected_dish_ids or [])
            if not check_ingredient_window_repeat(
                day_idx,
                base + [fid],
                plan_days,
                dish_ingredient_ids,
                max_ing_limit,
                window_active_days=ing_window_days,
                max_consecutive_days=max_ing_consec,
                no_same_within_day_keys=no_same_within_day,
            ):
                continue
        if check_fruit_window_repeat(day_idx, fid, plan_days, max_fruit_7):
            return fid

    return fruit_ids[day_idx % len(fruit_ids)]


def choose_soup(
    day_idx: int,
    soups: List[Dish],
    plan_days: List[PlanDay],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    main_id: str,
    dish_ingredient_ids: Optional[Dict[str, Set[str]]] = None,
    rng: Optional[random.Random] = None,
    topk: int = 25,
) -> Optional[str]:
    rep = _repeat_limits(hard)
    max_soup_7 = int(rep.get("max_same_soup_in_7_days", 1))
    max_ing_limit, ing_window_days, max_ing_consec, no_same_within_day = _ingredient_guardrails(hard)
    soup_ids = [d.id for d in soups if d.id in feat]

    soup_ids.sort(
        key=lambda did: (
            -feat[did].inventory_hit_ratio,
            999 if feat[did].near_expiry_days_min is None else feat[did].near_expiry_days_min,
            feat[did].cost_per_serving,
        )
    )

    if rng is not None and len(soup_ids) > 1:
        head = soup_ids[:topk]
        rng.shuffle(head)
        soup_ids = head + soup_ids[topk:]

    for sid in soup_ids:
        if dish_ingredient_ids is not None and not check_ingredient_window_repeat(
            day_idx,
            [main_id, sid],
            plan_days,
            dish_ingredient_ids,
            max_ing_limit,
            window_active_days=ing_window_days,
            max_consecutive_days=max_ing_consec,
            no_same_within_day_keys=no_same_within_day,
        ):
            continue
        if check_soup_window_repeat(day_idx, sid, plan_days, max_soup_7):
            return sid
    return None


def analyze_soup_rejections(
    day_idx: int,
    soups: List[Dish],
    plan_days: List[PlanDay],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    main_id: str,
    dish_ingredient_ids: Optional[Dict[str, Set[str]]] = None,
) -> Dict[str, int]:
    rep = _repeat_limits(hard)
    max_soup_7 = int(rep.get("max_same_soup_in_7_days", 1))
    max_ing_limit, ing_window_days, max_ing_consec, no_same_within_day = _ingredient_guardrails(hard)

    soup_ids = [d.id for d in soups if d.id in feat]
    blocked_by_ingredient = 0
    blocked_by_soup_repeat = 0
    feasible = 0

    for sid in soup_ids:
        ingredient_ok = True
        if dish_ingredient_ids is not None:
            ingredient_ok = check_ingredient_window_repeat(
                day_idx,
                [main_id, sid],
                plan_days,
                dish_ingredient_ids,
                max_ing_limit,
                window_active_days=ing_window_days,
                max_consecutive_days=max_ing_consec,
                no_same_within_day_keys=no_same_within_day,
            )

        if not ingredient_ok:
            blocked_by_ingredient += 1
            continue

        soup_repeat_ok = check_soup_window_repeat(day_idx, sid, plan_days, max_soup_7)
        if not soup_repeat_ok:
            blocked_by_soup_repeat += 1
            continue

        feasible += 1

    return {
        "candidate_count": len(soup_ids),
        "feasible_count": feasible,
        "blocked_by_ingredient_repeat": blocked_by_ingredient,
        "blocked_by_soup_repeat": blocked_by_soup_repeat,
        "max_same_ingredient_in_window_days": max_ing_limit,
        "ingredient_repeat_window_days": ing_window_days,
    }


def choose_sides_backtrack(
    day_idx: int,
    sides: List[Dish],
    plan_days: List[PlanDay],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    main_id: str,
    soup_id: str,
    fruit_id: str,
    dish_ingredient_ids: Optional[Dict[str, Set[str]]] = None,
    rng: Optional[random.Random] = None,
    topk: int = 120,
    pick_count: int = 2,
) -> Optional[List[str]]:
    rep = _repeat_limits(hard)
    max_side_7 = int(rep.get("max_same_side_in_7_days", 1))
    max_ing_limit, ing_window_days, max_ing_consec, no_same_within_day = _ingredient_guardrails(hard)
    side_ids = [d.id for d in sides if d.id in feat]

    side_ids.sort(
        key=lambda did: (
            -feat[did].inventory_hit_ratio,
            999 if feat[did].near_expiry_days_min is None else feat[did].near_expiry_days_min,
            feat[did].cost_per_serving,
        )
    )

    if rng is not None and len(side_ids) > 1:
        head = side_ids[:topk]
        rng.shuffle(head)
        side_ids = head

    chosen: List[str] = []

    def dfs(start_idx: int) -> Optional[List[str]]:
        if len(chosen) == pick_count:
            if not check_side_window_repeat(day_idx, chosen, plan_days, max_side_7):
                return None
            if dish_ingredient_ids is not None and not check_ingredient_window_repeat(
                day_idx,
                [main_id, soup_id, fruit_id] + list(chosen),
                plan_days,
                dish_ingredient_ids,
                max_ing_limit,
                window_active_days=ing_window_days,
                max_consecutive_days=max_ing_consec,
                no_same_within_day_keys=no_same_within_day,
            ):
                return None
            return list(chosen)

        for i in range(start_idx, len(side_ids)):
            did = side_ids[i]
            if did in chosen:
                continue
            chosen.append(did)
            res = dfs(i + 1)
            if res:
                return res
            chosen.pop()
        return None

    return dfs(0)


def choose_veg(
    day_idx: int,
    vegs: List[Dish],
    plan_days: List[PlanDay],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    selected_dish_ids: List[str],
    dish_ingredient_ids: Optional[Dict[str, Set[str]]] = None,
    rng: Optional[random.Random] = None,
    topk: int = 80,
) -> Optional[str]:
    rep = _repeat_limits(hard)
    max_veg_7 = int(rep.get("max_same_veg_in_7_days", rep.get("max_same_side_in_7_days", 1)))
    max_ing_limit, ing_window_days, max_ing_consec, no_same_within_day = _ingredient_guardrails(hard)
    veg_ids = [d.id for d in vegs if d.id in feat]

    veg_ids.sort(
        key=lambda did: (
            -feat[did].inventory_hit_ratio,
            999 if feat[did].near_expiry_days_min is None else feat[did].near_expiry_days_min,
            feat[did].cost_per_serving,
        )
    )

    if rng is not None and len(veg_ids) > 1:
        head = veg_ids[:topk]
        rng.shuffle(head)
        veg_ids = head + veg_ids[topk:]

    for vid in veg_ids:
        if dish_ingredient_ids is not None and not check_ingredient_window_repeat(
            day_idx,
            list(selected_dish_ids) + [vid],
            plan_days,
            dish_ingredient_ids,
            max_ing_limit,
            window_active_days=ing_window_days,
            max_consecutive_days=max_ing_consec,
            no_same_within_day_keys=no_same_within_day,
        ):
            continue
        if check_veg_window_repeat(day_idx, vid, plan_days, max_veg_7):
            return vid
    return None
