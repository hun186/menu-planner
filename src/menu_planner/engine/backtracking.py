# src/menu_planner/engine/backtracking.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple
import random

from ..db.repo import Dish
from .features import DishFeatures
from .constraints import PlanDay, check_main_hard, check_side_window_repeat, check_soup_window_repeat, check_cost_range
from .scoring import score_day

from .errors import PlanError

@dataclass
class BeamState:
    main_ids: List[str]
    main_meats: List[Optional[str]]
    weekly_meat_counts: Dict[int, Dict[str, int]]
    score: float


def plan_mains_beam(
    horizon_days: int,
    mains: List[Dish],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    beam_width: int,
    candidate_limit: int,
    seed: int = 7,
) -> List[str]:
    rng = random.Random(seed)

    # 候選先隨機打散，再用成本/庫存等排序（避免每次都一樣）
    main_ids = [d.id for d in mains if d.id in feat]
    rng.shuffle(main_ids)

    # 用 feature 做初步排序：偏好庫存 + 近到期 + 成本不要太極端
    def base_key(did: str) -> Tuple[float, float, float]:
        f = feat[did]
        inv = -f.inventory_hit_ratio
        near = 0.0 if f.near_expiry_days_min is None else (f.near_expiry_days_min / 10.0)
        cost = f.cost_per_serving / 200.0
        return (inv, near, cost)

    main_ids.sort(key=base_key)
    # 每天最多考慮的候選（加速）
    main_ids = main_ids[:max(candidate_limit, 10)]

    states: List[BeamState] = [BeamState(main_ids=[], main_meats=[], weekly_meat_counts={}, score=0.0)]

    for day in range(horizon_days):
        new_states: List[BeamState] = []

        for st in states:
            for did in main_ids:
                meat = feat[did].meat_type

                if not check_main_hard(
                    day_idx=day,
                    main_id=did,
                    main_meat_type=meat,
                    plan_main_ids=st.main_ids,
                    plan_main_meats=st.main_meats,
                    weekly_meat_counts=st.weekly_meat_counts,
                    hard=hard,
                ):
                    continue

                # 新狀態
                w = day // 7
                new_week_counts = {k: dict(v) for k, v in st.weekly_meat_counts.items()}
                if meat:
                    new_week_counts.setdefault(w, {})
                    new_week_counts[w][meat] = new_week_counts[w].get(meat, 0) + 1

                # main 階段先做「輕量分數」：重複主菜略扣、庫存/近到期略加
                s = st.score
                rep = st.main_ids.count(did) + 1
                if rep >= 2:
                    s += 5.0 * (rep - 1)  # 先用小扣分，真正分數在 day scoring

                f = feat[did]
                s += (-3.0 * f.inventory_hit_ratio)
                if f.near_expiry_days_min is not None and f.near_expiry_days_min <= 4:
                    s += -2.0

                new_states.append(
                    BeamState(
                        main_ids=st.main_ids + [did],
                        main_meats=st.main_meats + [meat],
                        weekly_meat_counts=new_week_counts,
                        score=s,
                    )
                )

        new_states.sort(key=lambda x: x.score)
        states = new_states[:beam_width]

        if not states:
            raise PlanError(
                code="MAIN_BEAM_NO_SOLUTION",
                day_index=day,
                message=f"主菜在第 {day+1} 天開始無可行解（hard 限制太嚴或主菜候選太少）。",
                details={
                    "beam_width": beam_width,
                    "candidate_limit": candidate_limit,
                    "hint": "可嘗試放寬週配額/連續同肉限制、提高主菜候選數或增加主菜資料。"
                }
            )
    return states[0].main_ids


def _pick_fruit(
    fruits: List[Dish],
    day_idx: int,
    feat: Dict[str, DishFeatures],
) -> str:
    # 水果允許重複，做個簡單輪替：依排序挑
    fruit_ids = [d.id for d in fruits if d.id in feat]
    fruit_ids.sort()
    if not fruit_ids:
        raise PlanError(code="FRUIT_EMPTY", message="找不到水果菜色。")
    return fruit_ids[day_idx % len(fruit_ids)]


def _choose_soup(
    day_idx: int,
    soups: List[Dish],
    plan_days: List[PlanDay],
    feat: Dict[str, DishFeatures],
    hard: Dict,
) -> Optional[str]:
    rep = hard.get("repeat_limits", {}) or {}
    max_soup_7 = int(rep.get("max_same_soup_in_7_days", 1))
    soup_ids = [d.id for d in soups if d.id in feat]

    # 優先：庫存命中高、近到期
    soup_ids.sort(key=lambda did: (-feat[did].inventory_hit_ratio,
                                  999 if feat[did].near_expiry_days_min is None else feat[did].near_expiry_days_min,
                                  feat[did].cost_per_serving))

    for sid in soup_ids:
        if check_soup_window_repeat(day_idx, sid, plan_days, max_soup_7):
            return sid
    return None


def _choose_sides_backtrack(
    day_idx: int,
    sides: List[Dish],
    plan_days: List[PlanDay],
    feat: Dict[str, DishFeatures],
    hard: Dict,
) -> Optional[List[str]]:
    rep = hard.get("repeat_limits", {}) or {}
    max_side_7 = int(rep.get("max_same_side_in_7_days", 1))
    side_ids = [d.id for d in sides if d.id in feat]

    # 排序：偏好庫存命中 + 近到期 + 低成本
    side_ids.sort(key=lambda did: (-feat[did].inventory_hit_ratio,
                                  999 if feat[did].near_expiry_days_min is None else feat[did].near_expiry_days_min,
                                  feat[did].cost_per_serving))

    # 小回溯選 3 道互不相同
    chosen: List[str] = []

    def dfs(start_idx: int) -> Optional[List[str]]:
        if len(chosen) == 3:
            if check_side_window_repeat(day_idx, chosen, plan_days, max_side_7):
                return list(chosen)
            return None

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


def fill_days_after_mains(
    horizon_days: int,
    main_ids: List[str],
    sides: List[Dish],
    soups: List[Dish],
    fruits: List[Dish],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    weights: Dict,
    soft: Dict,
) -> Tuple[List[PlanDay], float, List[Dict], List[Dict]]:
    plan_days: List[PlanDay] = []
    total_score = 0.0
    explanations: List[Dict] = []
    errors: List[Dict] = []

    prev_meat = None
    prev_cuisine = None

    rep = hard.get("repeat_limits", {}) or {}
    max_soup_7 = int(rep.get("max_same_soup_in_7_days", 1))
    max_side_7 = int(rep.get("max_same_side_in_7_days", 1))

    cr = (hard.get("cost_range_per_person_per_day") or {})
    cost_min = float(cr.get("min", 0))
    cost_max = float(cr.get("max", 10**18))

    for day in range(horizon_days):
        main_id = main_ids[day]

        # ===== fruit（若整個水果類別空，這屬於「系統性缺資料」，建議仍可 raise）=====
        # 你想「連水果都缺也繼續排」也行，但通常代表資料集不完整
        try:
            fruit_id = _pick_fruit(fruits, day, feat)
        except PlanError as e:
            # 系統性缺水果：仍可回傳 errors + placeholder 後繼續
            errors.append(e.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=[], soup="", fruit=""))
            explanations.append({
                "day_index": day,
                "failed": True,
                "reason_code": e.code,
                "message": e.message,
                "details": e.details or {}
            })
            continue

        # ===== soup =====
        soup_id = _choose_soup(day, soups, plan_days, feat, hard)
        if not soup_id:
            err = PlanError(
                code="SOUP_NO_SOLUTION",
                day_index=day,
                message=f"第 {day+1} 天找不到符合重複限制的湯。",
                details={
                    "max_same_soup_in_7_days": max_soup_7,
                    "hint": "可放寬湯品 7 天重複限制，或增加湯品候選。"
                }
            )
            errors.append(err.to_dict())
            # placeholder：主菜保留，其餘留空
            plan_days.append(PlanDay(main=main_id, sides=[], soup="", fruit=fruit_id))
            explanations.append({
                "day_index": day,
                "failed": True,
                "reason_code": err.code,
                "message": err.message,
                "details": err.details or {}
            })
            continue

        # ===== sides =====
        side_ids = _choose_sides_backtrack(day, sides, plan_days, feat, hard)
        if not side_ids:
            side_candidates = [d.id for d in sides if d.id in feat]
            err = PlanError(
                code="SIDE_NO_SOLUTION",
                day_index=day,
                message=f"第 {day+1} 天找不到符合重複限制的 3 道配菜。",
                details={
                    "max_same_side_in_7_days": max_side_7,
                    "candidate_count": len(side_candidates),
                    "hint": "可放寬配菜 7 天重複限制，或增加配菜候選。"
                }
            )
            errors.append(err.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=[], soup=soup_id, fruit=fruit_id))
            explanations.append({
                "day_index": day,
                "failed": True,
                "reason_code": err.code,
                "message": err.message,
                "details": err.details or {}
            })
            continue

        # ===== cost =====
        day_cost = (
            feat[main_id].cost_per_serving
            + feat[soup_id].cost_per_serving
            + feat[fruit_id].cost_per_serving
            + sum(feat[s].cost_per_serving for s in side_ids)
        )

        if not check_cost_range(day_cost, hard):
            # 嘗試替換湯/配菜以符合成本（簡單重試）
            ok = False

            # 重試湯
            for sid in [d.id for d in soups if d.id in feat]:
                if not check_soup_window_repeat(day, sid, plan_days, max_soup_7):
                    continue
                test_cost = (
                    feat[main_id].cost_per_serving
                    + feat[sid].cost_per_serving
                    + feat[fruit_id].cost_per_serving
                    + sum(feat[s].cost_per_serving for s in side_ids)
                )
                if check_cost_range(test_cost, hard):
                    soup_id = sid
                    day_cost = test_cost
                    ok = True
                    break

            # 重試配菜（改用另一組）
            if not ok:
                alt = _choose_sides_backtrack(day, sides[::-1], plan_days, feat, hard)  # 反向試一次
                if alt:
                    side_ids = alt
                    day_cost = (
                        feat[main_id].cost_per_serving
                        + feat[soup_id].cost_per_serving
                        + feat[fruit_id].cost_per_serving
                        + sum(feat[s].cost_per_serving for s in side_ids)
                    )
                    ok = check_cost_range(day_cost, hard)

            if not ok:
                err = PlanError(
                    code="COST_OUT_OF_RANGE",
                    day_index=day,
                    message=f"第 {day+1} 天成本 {day_cost:.2f} 超出區間 {cost_min:.2f}～{cost_max:.2f}。",
                    details={
                        "day_cost": round(day_cost, 2),
                        "range": {"min": cost_min, "max": cost_max},
                        "items": {"main": main_id, "soup": soup_id, "fruit": fruit_id, "sides": side_ids},
                        "cost_breakdown": {
                            "main": round(feat[main_id].cost_per_serving, 2),
                            "soup": round(feat[soup_id].cost_per_serving, 2),
                            "fruit": round(feat[fruit_id].cost_per_serving, 2),
                            "sides": [round(feat[s].cost_per_serving, 2) for s in side_ids],
                        },
                        "hint": "可提高成本上限、增加低成本候選、或放寬湯/配菜重複限制以擴大可替換組合。"
                    }
                )
                errors.append(err.to_dict())
                # placeholder：主菜/湯/果保留，配菜清空（代表當天未完成）
                plan_days.append(PlanDay(main=main_id, sides=[], soup=soup_id, fruit=fruit_id))
                explanations.append({
                    "day_index": day,
                    "failed": True,
                    "reason_code": err.code,
                    "message": err.message,
                    "details": err.details or {},
                    "cost": round(day_cost, 2),
                })
                continue

        # ===== success day =====
        day_obj = PlanDay(main=main_id, sides=side_ids, soup=soup_id, fruit=fruit_id)

        chosen = {
            "main": feat[main_id],
            "side1": feat[side_ids[0]],
            "side2": feat[side_ids[1]],
            "side3": feat[side_ids[2]],
            "soup": feat[soup_id],
            "fruit": feat[fruit_id],
        }
        ctx = {
            "prev_main_meat": prev_meat,
            "prev_main_cuisine": prev_cuisine,
            "prefer_use_inventory": bool(soft.get("prefer_use_inventory", False)),
            "prefer_near_expiry": bool(soft.get("prefer_near_expiry", False)),
        }
        sb = score_day(day_cost=day_cost, hard=hard, weights=weights, chosen=chosen, context=ctx)

        total_score += sb.total
        plan_days.append(day_obj)
        explanations.append({
            "day_index": day,
            "failed": False,
            "cost": round(day_cost, 2),
            "score": sb.total,
            "score_breakdown": sb.items,
            "main_meat_type": chosen["main"].meat_type,
            "inventory_used": {
                "main": chosen["main"].used_inventory_ingredients,
                "soup": chosen["soup"].used_inventory_ingredients,
                "sides": [
                    chosen["side1"].used_inventory_ingredients,
                    chosen["side2"].used_inventory_ingredients,
                    chosen["side3"].used_inventory_ingredients,
                ]
            }
        })

        prev_meat = chosen["main"].meat_type
        prev_cuisine = chosen["main"].cuisine

    return plan_days, round(total_score, 2), explanations, errors

'''
def fill_days_after_mains_0210(
    horizon_days: int,
    main_ids: List[str],
    sides: List[Dish],
    soups: List[Dish],
    fruits: List[Dish],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    weights: Dict,
    soft: Dict,
) -> Tuple[List[PlanDay], float, List[Dict]]:
    plan_days: List[PlanDay] = []
    total_score = 0.0
    explanations: List[Dict] = []

    prev_meat = None
    prev_cuisine = None

    for day in range(horizon_days):
        main_id = main_ids[day]
        fruit_id = _pick_fruit(fruits, day, feat)

        soup_id = _choose_soup(day, soups, plan_days, feat, hard)
        if not soup_id:
            rep = hard.get("repeat_limits", {}) or {}
            raise PlanError(
                code="SOUP_NO_SOLUTION",
                day_index=day,
                message=f"第 {day+1} 天找不到符合重複限制的湯。",
                details={
                    "max_same_soup_in_7_days": int(rep.get("max_same_soup_in_7_days", 1)),
                    "hint": "可放寬湯品 7 天重複限制，或增加湯品候選。"
                }
            )

        side_ids = _choose_sides_backtrack(day, sides, plan_days, feat, hard)
        if not side_ids:
            rep = hard.get("repeat_limits", {}) or {}
            raise PlanError(
                code="SIDE_NO_SOLUTION",
                day_index=day,
                message=f"第 {day+1} 天找不到符合重複限制的 3 道配菜。",
                details={
                    "max_same_side_in_7_days": int(rep.get("max_same_side_in_7_days", 1)),
                    "hint": "可放寬配菜 7 天重複限制，或增加配菜候選。"
                }
            )

        # 成本 hard：主+3配+湯+果
        day_cost = (
            feat[main_id].cost_per_serving
            + feat[soup_id].cost_per_serving
            + feat[fruit_id].cost_per_serving
            + sum(feat[s].cost_per_serving for s in side_ids)
        )

        if not check_cost_range(day_cost, hard):
            # 嘗試替換湯/配菜以符合成本（簡單重試）
            ok = False
            # 重試湯
            for sid in [d.id for d in soups if d.id in feat]:
                if not check_soup_window_repeat(day, sid, plan_days, int((hard.get("repeat_limits") or {}).get("max_same_soup_in_7_days", 1))):
                    continue
                test_cost = feat[main_id].cost_per_serving + feat[sid].cost_per_serving + feat[fruit_id].cost_per_serving + sum(feat[s].cost_per_serving for s in side_ids)
                if check_cost_range(test_cost, hard):
                    soup_id = sid
                    day_cost = test_cost
                    ok = True
                    break
            # 重試配菜（改用另一組）
            if not ok:
                alt = _choose_sides_backtrack(day, sides[::-1], plan_days, feat, hard)  # 反向試一次
                if alt:
                    side_ids = alt
                    day_cost = feat[main_id].cost_per_serving + feat[soup_id].cost_per_serving + feat[fruit_id].cost_per_serving + sum(feat[s].cost_per_serving for s in side_ids)
                    ok = check_cost_range(day_cost, hard)

            if not ok:
                cr = (hard.get("cost_range_per_person_per_day") or {})
                mn = float(cr.get("min", 0))
                mx = float(cr.get("max", 10**18))
            
                raise PlanError(
                    code="COST_OUT_OF_RANGE",
                    day_index=day,
                    message=f"第 {day+1} 天成本 {day_cost:.2f} 超出區間 {mn:.2f}～{mx:.2f}。",
                    details={
                        "day_cost": round(day_cost, 2),
                        "range": {"min": mn, "max": mx},
                        "items": {
                            "main": main_id,
                            "soup": soup_id,
                            "fruit": fruit_id,
                            "sides": side_ids,
                        },
                        "cost_breakdown": {
                            "main": round(feat[main_id].cost_per_serving, 2),
                            "soup": round(feat[soup_id].cost_per_serving, 2),
                            "fruit": round(feat[fruit_id].cost_per_serving, 2),
                            "sides": [round(feat[s].cost_per_serving, 2) for s in side_ids],
                        },
                        "hint": "可提高成本上限、增加低成本候選、或放寬湯/配菜重複限制以擴大可替換組合。"
                    }
                )

        day_obj = PlanDay(main=main_id, sides=side_ids, soup=soup_id, fruit=fruit_id)

        chosen = {
            "main": feat[main_id],
            "side1": feat[side_ids[0]],
            "side2": feat[side_ids[1]],
            "side3": feat[side_ids[2]],
            "soup": feat[soup_id],
            "fruit": feat[fruit_id],
        }
        ctx = {
            "prev_main_meat": prev_meat,
            "prev_main_cuisine": prev_cuisine,
            "prefer_use_inventory": bool(soft.get("prefer_use_inventory", False)),
            "prefer_near_expiry": bool(soft.get("prefer_near_expiry", False)),
        }
        sb = score_day(day_cost=day_cost, hard=hard, weights=weights, chosen=chosen, context=ctx)

        total_score += sb.total
        plan_days.append(day_obj)
        explanations.append({
            "day_index": day,
            "cost": round(day_cost, 2),
            "score": sb.total,
            "score_breakdown": sb.items,
            "main_meat_type": chosen["main"].meat_type,
            "inventory_used": {
                "main": chosen["main"].used_inventory_ingredients,
                "soup": chosen["soup"].used_inventory_ingredients,
                "sides": [
                    chosen["side1"].used_inventory_ingredients,
                    chosen["side2"].used_inventory_ingredients,
                    chosen["side3"].used_inventory_ingredients,
                ]
            }
        })

        prev_meat = chosen["main"].meat_type
        prev_cuisine = chosen["main"].cuisine

    return plan_days, round(total_score, 2), explanations
'''