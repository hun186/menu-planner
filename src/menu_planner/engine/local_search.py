# src/menu_planner/engine/local_search.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import random
from datetime import date, timedelta

from ..db.repo import Dish
from .constraints import PlanDay, check_cost_range, check_soup_window_repeat, check_side_window_repeat, check_main_hard
from .features import DishFeatures
from .scoring import score_day

def _week_key_of(day_idx: int, start_date: Optional[date]) -> int:
    """與 beam/fill 一致：用真實日期 ISO week 當週 key；沒給 start_date 才退回 day//7。"""
    if start_date is None:
        return day_idx // 7
    iso = (start_date + timedelta(days=day_idx)).isocalendar()
    return iso.year * 100 + iso.week
    
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
        # ✅ 不排日：不計分、不影響 prev_*（讓連續肉判斷更合理）
        if not d.main:
            day_details.append({
                "day_index": day_idx,
                "cost": 0,
                "score": 0,
                "score_breakdown": {},
                "is_offday": True,
            })
            continue

        # ✅ 不完整：直接視為 hard 破壞（local search 會跳過）
        if (not d.soup) or (not d.fruit) or (not d.sides) or (len(d.sides) != 3):
            return (10**18, [])

        # ✅ id 必須存在於 feat（避免 KeyError）
        if (d.main not in feat) or (d.soup not in feat) or (d.fruit not in feat) or any(s not in feat for s in d.sides):
            return (10**18, [])

        day_cost = (
            feat[d.main].cost_per_serving
            + feat[d.soup].cost_per_serving
            + feat[d.fruit].cost_per_serving
            + sum(feat[s].cost_per_serving for s in d.sides)
        )
        if not check_cost_range(day_cost, hard):
            return (10**18, [])  # hard 破了

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
            "is_offday": False,
        })

        prev_meat = chosen["main"].meat_type
        prev_cuisine = chosen["main"].cuisine

    return round(total, 2), day_details


def _hard_ok_for_plan(
    plan_days: List[PlanDay],
    mains: List[Dish],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    start_date: Optional[date] = None,   # ✅ 新增
) -> bool:
    # 重新走一次 main hard（週配額/連續肉/重複主菜）
    plan_main_ids: List[str] = []
    plan_main_meats: List[Optional[str]] = []
    weekly_meat_counts: Dict[int, Dict[str, int]] = {}

    for day_idx, d in enumerate(plan_days):
        # ✅ 不排日跳過：不計入週配額/連續肉/重複主菜
        if not d.main:
            continue

        if d.main not in feat:
            return False

        meat = feat[d.main].meat_type
        week_key = _week_key_of(day_idx, start_date)  # ✅ ISO week

        # ✅ check_main_hard 必須支援 week_key（你 beam 那邊已經在傳）
        if not check_main_hard(
            day_idx=day_idx,
            main_id=d.main,
            main_meat_type=meat,
            plan_main_ids=plan_main_ids,
            plan_main_meats=plan_main_meats,
            weekly_meat_counts=weekly_meat_counts,
            hard=hard,
            week_key=week_key,
        ):
            return False

        # apply（用同一個 week_key）
        weekly_meat_counts.setdefault(week_key, {})
        if meat:
            weekly_meat_counts[week_key][meat] = weekly_meat_counts[week_key].get(meat, 0) + 1

        plan_main_ids.append(d.main)
        plan_main_meats.append(meat)

    # side/soup window repeat
    rep = hard.get("repeat_limits", {}) or {}
    max_side_7 = int(rep.get("max_same_side_in_7_days", 1))
    max_soup_7 = int(rep.get("max_same_soup_in_7_days", 1))

    for day_idx, d in enumerate(plan_days):
        if not d.main:
            continue

        # ✅ 不完整直接視為不合法
        if (not d.sides) or (len(d.sides) != 3) or (not d.soup):
            return False

        # 這裡先保持你原本的語意（用 calendar day 的 day_idx & slice）
        # 若 check_* 內部沒有處理空白項目，建議也在 check_* 裡跳過空白 soup/side
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
    seed: int = 7,
    start_date: Optional[date] = None,
    active_mask: Optional[List[bool]] = None,   # ✅ 新增：接住 planner.py 傳入
) -> Tuple[List[PlanDay], float, List[Dict]]:
    rng = random.Random(seed)

    main_ids_all = [d.id for d in mains if d.id in feat]
    side_ids_all = [d.id for d in sides if d.id in feat]
    soup_ids_all = [d.id for d in soups if d.id in feat]
    fruit_ids_all = [d.id for d in fruits if d.id in feat]

    # ✅ active 日索引（若沒傳 active_mask，就視為全 active）
    if active_mask and len(active_mask) == len(plan_days):
        active_indices = [i for i, on in enumerate(active_mask) if on]
    else:
        active_indices = list(range(len(plan_days)))

    # 若根本沒有 active 日，直接回傳
    if not active_indices:
        best_score, best_details = compute_total_score(plan_days, feat, hard, weights, soft)
        return plan_days, best_score, best_details

    # 初始解
    best_plan = [PlanDay(d.main, list(d.sides), d.soup, d.fruit) for d in plan_days]
    best_score, best_details = compute_total_score(best_plan, feat, hard, weights, soft)

    cur_plan = [PlanDay(d.main, list(d.sides), d.soup, d.fruit) for d in best_plan]
    cur_score = best_score

    for _ in range(iterations):
        cand = [PlanDay(d.main, list(d.sides), d.soup, d.fruit) for d in cur_plan]
        op = rng.choice(["swap_main", "replace_main", "replace_soup", "replace_side"])

        # ✅ 只抽 active 日
        day_a = rng.choice(active_indices)
        day_b = rng.choice(active_indices)

        if op == "swap_main":
            if day_a == day_b:
                continue
            cand[day_a].main, cand[day_b].main = cand[day_b].main, cand[day_a].main

        elif op == "replace_main":
            cand[day_a].main = rng.choice(main_ids_all)

        elif op == "replace_soup":
            # active 日必須是完整日，不然直接跳過
            if not cand[day_a].main:
                continue
            cand[day_a].soup = rng.choice(soup_ids_all)

        elif op == "replace_side":
            if not cand[day_a].main:
                continue
            if len(cand[day_a].sides) < 3:
                continue
            i = rng.randrange(0, 3)
            cand[day_a].sides[i] = rng.choice(side_ids_all)
            for _t in range(5):
                if len(set(cand[day_a].sides)) == 3:
                    break
                cand[day_a].sides[i] = rng.choice(side_ids_all)

        # ✅ 關鍵：硬限制檢查（含 ISO week）+ 不排日跳過（在 _hard_ok_for_plan 內做）
        if not _hard_ok_for_plan(cand, mains, feat, hard, start_date=start_date):
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