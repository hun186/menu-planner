# src/menu_planner/engine/local_search.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import random

from ..db.repo import Dish
from .constraints import PlanDay, check_cost_range, check_soup_window_repeat, check_side_window_repeat, check_main_hard
from .features import DishFeatures
from .scoring import score_day


def compute_total_score(
    plan_days: List[PlanDay],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    weights: Dict,
    soft: Dict,
) -> Tuple[float, List[Dict]]:
    total = 0.0
    day_details: List[Dict] = []
    prev_meat = None
    prev_cuisine = None

    for day_idx, d in enumerate(plan_days):
        day_cost = (
            feat[d.main].cost_per_serving
            + feat[d.soup].cost_per_serving
            + feat[d.fruit].cost_per_serving
            + sum(feat[s].cost_per_serving for s in d.sides)
        )
        if not check_cost_range(day_cost, hard):
            return (10**18, [])  # hard 破了，回一個極大分數

        chosen = {
            "main": feat[d.main],
            "side1": feat[d.sides[0]],
            "side2": feat[d.sides[1]],
            "side3": feat[d.sides[2]],
            "soup": feat[d.soup],
            "fruit": feat[d.fruit],
        }
        ctx = {
            "prev_main_meat": prev_meat,
            "prev_main_cuisine": prev_cuisine,
            "prefer_use_inventory": bool(soft.get("prefer_use_inventory", False)),
            "prefer_near_expiry": bool(soft.get("prefer_near_expiry", False)),
        }
        sb = score_day(day_cost, hard, weights, chosen, ctx)
        total += sb.total
        day_details.append({
            "day_index": day_idx,
            "cost": round(day_cost, 2),
            "score": sb.total,
            "score_breakdown": sb.items,
        })
        prev_meat = chosen["main"].meat_type
        prev_cuisine = chosen["main"].cuisine

    return round(total, 2), day_details


def _hard_ok_for_plan(
    plan_days: List[PlanDay],
    mains: List[Dish],
    feat: Dict[str, DishFeatures],
    hard: Dict,
) -> bool:
    # 重新走一次 main hard（週配額/連續肉/重複主菜）
    plan_main_ids: List[str] = []
    plan_main_meats: List[Optional[str]] = []
    weekly_meat_counts: Dict[int, Dict[str, int]] = {}

    for day_idx, d in enumerate(plan_days):
        meat = feat[d.main].meat_type
        if not check_main_hard(day_idx, d.main, meat, plan_main_ids, plan_main_meats, weekly_meat_counts, hard):
            return False
        # apply
        w = day_idx // 7
        weekly_meat_counts.setdefault(w, {})
        if meat:
            weekly_meat_counts[w][meat] = weekly_meat_counts[w].get(meat, 0) + 1
        plan_main_ids.append(d.main)
        plan_main_meats.append(meat)

    # side/soup window repeat
    rep = hard.get("repeat_limits", {}) or {}
    max_side_7 = int(rep.get("max_same_side_in_7_days", 1))
    max_soup_7 = int(rep.get("max_same_soup_in_7_days", 1))

    for day_idx, d in enumerate(plan_days):
        if not check_side_window_repeat(day_idx, d.sides, plan_days[:day_idx], max_side_7):
            return False
        if not check_soup_window_repeat(day_idx, d.soup, plan_days[:day_idx], max_soup_7):
            return False

    return True


def improve_by_local_search(
    plan_days: List[PlanDay],
    mains: List[Dish],
    sides: List[Dish],
    soups: List[Dish],
    fruits: List[Dish],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    weights: Dict,
    soft: Dict,
    iterations: int,
    accept_worse_probability: float,
    seed: int = 7
) -> Tuple[List[PlanDay], float, List[Dict]]:
    rng = random.Random(seed)

    main_ids_all = [d.id for d in mains if d.id in feat]
    side_ids_all = [d.id for d in sides if d.id in feat]
    soup_ids_all = [d.id for d in soups if d.id in feat]
    fruit_ids_all = [d.id for d in fruits if d.id in feat]

    best_plan = [PlanDay(d.main, list(d.sides), d.soup, d.fruit) for d in plan_days]
    best_score, best_details = compute_total_score(best_plan, feat, hard, weights, soft)

    cur_plan = [PlanDay(d.main, list(d.sides), d.soup, d.fruit) for d in best_plan]
    cur_score, _ = best_score, best_details

    for _ in range(iterations):
        cand = [PlanDay(d.main, list(d.sides), d.soup, d.fruit) for d in cur_plan]
        op = rng.choice(["swap_main", "replace_main", "replace_soup", "replace_side"])

        day_a = rng.randrange(0, len(cand))
        day_b = rng.randrange(0, len(cand))

        if op == "swap_main" and day_a != day_b:
            cand[day_a].main, cand[day_b].main = cand[day_b].main, cand[day_a].main

        elif op == "replace_main":
            cand[day_a].main = rng.choice(main_ids_all)

        elif op == "replace_soup":
            cand[day_a].soup = rng.choice(soup_ids_all)

        elif op == "replace_side":
            i = rng.randrange(0, 3)
            cand[day_a].sides[i] = rng.choice(side_ids_all)
            # 同一天 side 去重（若撞到就再抽幾次）
            for _t in range(5):
                if len(set(cand[day_a].sides)) == 3:
                    break
                cand[day_a].sides[i] = rng.choice(side_ids_all)

        if not _hard_ok_for_plan(cand, mains, feat, hard):
            continue

        cand_score, cand_details = compute_total_score(cand, feat, hard, weights, soft)

        if cand_score < cur_score:
            cur_plan, cur_score = cand, cand_score
            if cand_score < best_score:
                best_plan, best_score, best_details = cand, cand_score, cand_details
        else:
            if rng.random() < accept_worse_probability:
                cur_plan, cur_score = cand, cand_score

    return best_plan, best_score, best_details
