# src/menu_planner/engine/backtracking.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from datetime import timedelta
from typing import Dict, List, Optional, Set, Tuple
import random

from ..db.repo import Dish
from .features import DishFeatures
from .constraints import PlanDay, check_main_hard 
from .constraints import (
    check_side_window_repeat,
    check_soup_window_repeat,
    check_fruit_window_repeat,
    check_veg_window_repeat,
    check_ingredient_window_repeat,
)
from .constraints import check_cost_range
from .scoring import score_day

from .errors import PlanError


def _failed_day_explanation(
    *,
    day_index: int,
    reason_code: str,
    message: str,
    details: Optional[Dict] = None,
    cost: Optional[float] = None,
) -> Dict:
    return {
        "day_index": day_index,
        "failed": True,
        "reason_code": reason_code,
        "message": message,
        "details": details or {},
        "cost": cost,
        "score": None,
        "score_breakdown": {},
        "score_fitness": None,
        "score_bonus_total": None,
        "score_penalty_total": None,
        "score_summary": None,
    }

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
    start_date: Optional[date] = None,
    active_mask: Optional[List[bool]] = None,
) -> List[str]:
    rng = random.Random(seed)

    # 候選先隨機打散，再用成本/庫存等排序
    main_ids = [d.id for d in mains if d.id in feat]
    rng.shuffle(main_ids)

    def base_key(did: str) -> Tuple[float, float, float]:
        f = feat[did]
        inv = -f.inventory_hit_ratio
        near = 0.0 if f.near_expiry_days_min is None else (f.near_expiry_days_min / 10.0)
        cost = f.cost_per_serving / 200.0
        return (inv, near, cost)

    main_ids.sort(key=base_key)
    #main_ids = main_ids[:max(candidate_limit, 100)]

    states: List[BeamState] = [
        BeamState(main_ids=[], main_meats=[], weekly_meat_counts={}, score=0.0)
    ]

    # active_mask 長度防呆：不足就視為全 active
    use_mask = active_mask if (active_mask and len(active_mask) >= horizon_days) else None

    for day in range(horizon_days):
        new_states: List[BeamState] = []

        is_active = True if use_mask is None else bool(use_mask[day])

        # ✅ 不排日：延續狀態 + placeholder（不計入連續/配額）
        if not is_active:
            for st in states:
                new_states.append(
                    BeamState(
                        main_ids=st.main_ids + [""],
                        main_meats=st.main_meats + [None],
                        weekly_meat_counts=st.weekly_meat_counts,  # 不變
                        score=st.score,
                    )
                )
            states = new_states[:beam_width]
            continue

        # ✅ 排程日：計算 week_key（用真實日期的 ISO week）
        if start_date is None:
            week_key = day // 7
        else:
            iso = (start_date + timedelta(days=day)).isocalendar()
            week_key = iso.year * 100 + iso.week  # 例如 202605

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
                    week_key=week_key,  # ✅ 關鍵：把真實週傳進去
                    start_date=start_date,   # ✅ 新增這行
                ):
                    continue

                # 新狀態：週計數也用同一個 week_key
                new_week_counts = {k: dict(v) for k, v in st.weekly_meat_counts.items()}
                if meat:
                    new_week_counts.setdefault(week_key, {})
                    new_week_counts[week_key][meat] = new_week_counts[week_key].get(meat, 0) + 1

                # main 階段輕量分數
                s = st.score
                rep = st.main_ids.count(did) + 1
                if rep >= 2:
                    s += 5.0 * (rep - 1)

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
        #print("states",states)

        if not states:
            cur_date = start_date + timedelta(days=day)
            print("NO SOLUTION AT:", day+1, cur_date.isoformat(), "weekday", cur_date.isoweekday())
            print("fixed rule:", (hard.get("fixed_main_meat_by_weekday") or {}).get(str(cur_date.isoweekday())))
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

'''
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
'''

def _pick_fruit(
    fruits: List[Dish],
    day_idx: int,
    plan_days: List[PlanDay],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    dish_ingredient_ids: Optional[Dict[str, Set[str]]] = None,
    selected_dish_ids: Optional[List[str]] = None,
) -> str:
    rep = hard.get("repeat_limits", {}) or {}
    max_fruit_7 = int(rep.get("max_same_fruit_in_7_days", 10**9))  # 預設幾乎不限制
    max_ing_7 = int(rep.get("max_same_ingredient_in_7_days", 10**9))

    fruit_ids = [d.id for d in fruits if d.id in feat]
    if not fruit_ids:
        raise PlanError(code="FRUIT_EMPTY", message="找不到水果菜色。")

    # ✅ 不要 sort，保留外部傳入的順序（你已在外面 shuffle）
    for fid in fruit_ids:
        if dish_ingredient_ids is not None:
            base = list(selected_dish_ids or [])
            if not check_ingredient_window_repeat(day_idx, base + [fid], plan_days, dish_ingredient_ids, max_ing_7):
                continue
        if check_fruit_window_repeat(day_idx, fid, plan_days, max_fruit_7):
            return fid

    # 都不符合時：退一步給個 fallback（避免整天失敗）
    return fruit_ids[day_idx % len(fruit_ids)]

def _choose_soup(
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
    rep = hard.get("repeat_limits", {}) or {}
    max_soup_7 = int(rep.get("max_same_soup_in_7_days", 1))
    max_ing_7 = int(rep.get("max_same_ingredient_in_7_days", 10**9))
    soup_ids = [d.id for d in soups if d.id in feat]

    soup_ids.sort(key=lambda did: (
        -feat[did].inventory_hit_ratio,
        999 if feat[did].near_expiry_days_min is None else feat[did].near_expiry_days_min,
        feat[did].cost_per_serving
    ))

    # ✅ 打散前 topk，避免永遠選到同一批第一名
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
            max_ing_7,
        ):
            continue
        if check_soup_window_repeat(day_idx, sid, plan_days, max_soup_7):
            return sid
    return None


def _choose_sides_backtrack(
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
    rep = hard.get("repeat_limits", {}) or {}
    max_side_7 = int(rep.get("max_same_side_in_7_days", 1))
    max_ing_7 = int(rep.get("max_same_ingredient_in_7_days", 10**9))
    side_ids = [d.id for d in sides if d.id in feat]

    side_ids.sort(key=lambda did: (
        -feat[did].inventory_hit_ratio,
        999 if feat[did].near_expiry_days_min is None else feat[did].near_expiry_days_min,
        feat[did].cost_per_serving
    ))

    # ✅ 打散 topk（也可順便縮小搜尋空間，加速回溯）
    if rng is not None and len(side_ids) > 1:
        head = side_ids[:topk]
        rng.shuffle(head)
        side_ids = head  # 直接用 topk 當候選池（通常更穩、更快）

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
                max_ing_7,
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


def _choose_veg(
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
    rep = hard.get("repeat_limits", {}) or {}
    max_veg_7 = int(rep.get("max_same_veg_in_7_days", rep.get("max_same_side_in_7_days", 1)))
    max_ing_7 = int(rep.get("max_same_ingredient_in_7_days", 10**9))
    veg_ids = [d.id for d in vegs if d.id in feat]

    veg_ids.sort(key=lambda did: (
        -feat[did].inventory_hit_ratio,
        999 if feat[did].near_expiry_days_min is None else feat[did].near_expiry_days_min,
        feat[did].cost_per_serving
    ))

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
            max_ing_7,
        ):
            continue
        if check_veg_window_repeat(day_idx, vid, plan_days, max_veg_7):
            return vid
    return None


def fill_days_after_mains(
    horizon_days: int,
    main_ids: List[str],
    sides: List[Dish],
    vegs: List[Dish],
    soups: List[Dish],
    fruits: List[Dish],
    feat: Dict[str, DishFeatures],
    hard: Dict,
    weights: Dict,
    soft: Dict,
    dish_ingredient_ids: Optional[Dict[str, Set[str]]] = None,
    start_date: Optional[date] = None,          # ✅ 新增（可選）
    active_mask: Optional[List[bool]] = None,   # ✅ 新增（可選）
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

    side_pool0  = [d for d in sides  if d.id in feat]
    veg_pool0   = [d for d in vegs   if d.id in feat]
    soup_pool0  = [d for d in soups  if d.id in feat]
    fruit_pool0 = [d for d in fruits if d.id in feat]
    
    print("usable sides (in feat):", len(side_pool0), "/", len(sides))
    print("usable vegs  (in feat):", len(veg_pool0), "/", len(vegs))
    print("usable soups (in feat):", len(soup_pool0), "/", len(soups))
    print("usable fruits(in feat):", len(fruit_pool0), "/", len(fruits))

    for day in range(horizon_days):
        main_id = main_ids[day]
        if not main_id:
            plan_days.append(PlanDay(main="", sides=[], veg="", soup="", fruit=""))
            explanations.append({
                "day_index": day,
                "failed": False,
                "is_offday": True,
                "message": "非排程日（休息/不排）",
                "cost": 0,
                "score": 0,
                "score_breakdown": {},
                "score_fitness": 0,
                "score_bonus_total": 0,
                "score_penalty_total": 0,
                "score_summary": {"bonus": 0, "penalty": 0, "raw": 0, "fitness": 0},
            })
            continue
        
        seed0 = int(hard.get("seed", 7))  # 或改成 cfg seed 傳進來
        rng = random.Random(seed0 + day * 10007)
        
        # 只拿可用候選（在 feat 裡）
        fruit_pool = fruit_pool0[:]
        soup_pool  = soup_pool0[:]
        side_pool  = side_pool0[:]
        veg_pool   = veg_pool0[:]
        
        rng.shuffle(fruit_pool)
        rng.shuffle(soup_pool)
        rng.shuffle(side_pool)
        rng.shuffle(veg_pool)
        
        # ===== fruit（若整個水果類別空，這屬於「系統性缺資料」，建議仍可 raise）=====
        # 你想「連水果都缺也繼續排」也行，但通常代表資料集不完整
        try:
            #fruit_id = _pick_fruit(fruits, day, feat)
            #fruit_id = _pick_fruit(fruit_pool, day, feat)
            fruit_id = _pick_fruit(
                fruit_pool,
                day,
                plan_days,
                feat,
                hard,
                dish_ingredient_ids=dish_ingredient_ids,
                selected_dish_ids=[main_id],
            )
        except PlanError as e:
            # 系統性缺水果：仍可回傳 errors + placeholder 後繼續
            errors.append(e.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup="", fruit=""))
            explanations.append(
                _failed_day_explanation(
                    day_index=day,
                    reason_code=e.code,
                    message=e.message,
                    details=e.details,
                )
            )
            continue

        # ===== soup =====
        #soup_id = _choose_soup(day, soups, plan_days, feat, hard)
        #soup_id  = _choose_soup(day, soup_pool, plan_days, feat, hard)
        soup_id  = _choose_soup(
            day,
            soup_pool,
            plan_days,
            feat,
            hard,
            main_id=main_id,
            dish_ingredient_ids=dish_ingredient_ids,
            rng=rng,
        )
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
            plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup="", fruit=fruit_id))
            explanations.append(
                _failed_day_explanation(
                    day_index=day,
                    reason_code=err.code,
                    message=err.message,
                    details=err.details,
                )
            )
            continue

        # ===== sides =====
        #side_ids = _choose_sides_backtrack(day, sides, plan_days, feat, hard)
        #side_ids = _choose_sides_backtrack(day, side_pool, plan_days, feat, hard)
        side_ids = _choose_sides_backtrack(
            day,
            side_pool,
            plan_days,
            feat,
            hard,
            main_id=main_id,
            soup_id=soup_id,
            fruit_id=fruit_id,
            dish_ingredient_ids=dish_ingredient_ids,
            rng=rng,
            pick_count=2,
        )
        if not side_ids:
            side_candidates = [d.id for d in sides if d.id in feat]
            err = PlanError(
                code="SIDE_NO_SOLUTION",
                day_index=day,
                message=f"第 {day+1} 天找不到符合重複限制的 2 道配菜。",
                details={
                    "max_same_side_in_7_days": max_side_7,
                    "candidate_count": len(side_candidates),
                    "hint": "可放寬配菜 7 天重複限制，或增加配菜候選。"
                }
            )
            errors.append(err.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup=soup_id, fruit=fruit_id))
            explanations.append(
                _failed_day_explanation(
                    day_index=day,
                    reason_code=err.code,
                    message=err.message,
                    details=err.details,
                )
            )
            continue

        veg_id = _choose_veg(
            day,
            veg_pool,
            plan_days,
            feat,
            hard,
            selected_dish_ids=[main_id, soup_id, fruit_id] + list(side_ids),
            dish_ingredient_ids=dish_ingredient_ids,
            rng=rng,
        )
        if not veg_id:
            err = PlanError(
                code="VEG_NO_SOLUTION",
                day_index=day,
                message=f"第 {day+1} 天找不到符合重複限制的蔬菜。",
                details={
                    "max_same_veg_in_7_days": int(rep.get("max_same_veg_in_7_days", max_side_7)),
                    "candidate_count": len([d.id for d in vegs if d.id in feat]),
                    "hint": "可放寬 veg 7 天重複限制（或沿用 side 限制），或增加 veg 候選。"
                }
            )
            errors.append(err.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=side_ids, veg="", soup=soup_id, fruit=fruit_id))
            explanations.append(
                _failed_day_explanation(
                    day_index=day,
                    reason_code=err.code,
                    message=err.message,
                    details=err.details,
                )
            )
            continue

        # ===== cost =====
        day_cost = (
            feat[main_id].cost_per_serving
            + feat[soup_id].cost_per_serving
            + feat[fruit_id].cost_per_serving
            + feat[veg_id].cost_per_serving
            + sum(feat[s].cost_per_serving for s in side_ids)
        )

        if not check_cost_range(day_cost, hard):
            # 嘗試替換湯/配菜以符合成本（簡單重試）
            ok = False

            # 重試湯
            #for sid in [d.id for d in soups if d.id in feat]:
            # 重試湯：改用 soup_pool（已打散）
            for d in soup_pool:
                sid = d.id
                if not check_soup_window_repeat(day, sid, plan_days, max_soup_7):
                    continue
                test_cost = (
                    feat[main_id].cost_per_serving
                    + feat[sid].cost_per_serving
                    + feat[fruit_id].cost_per_serving
                    + feat[veg_id].cost_per_serving
                    + sum(feat[s].cost_per_serving for s in side_ids)
                )
                if check_cost_range(test_cost, hard):
                    soup_id = sid
                    day_cost = test_cost
                    ok = True
                    break

            # 重試配菜（改用另一組）
            if not ok:
                #alt = _choose_sides_backtrack(day, sides[::-1], plan_days, feat, hard)  # 反向試一次
                alt_pool = side_pool[:]
                rng.shuffle(alt_pool)
                #alt = _choose_sides_backtrack(day, alt_pool, plan_days, feat, hard)
                alt = _choose_sides_backtrack(
                    day,
                    alt_pool,
                    plan_days,
                    feat,
                    hard,
                    main_id=main_id,
                    soup_id=soup_id,
                    fruit_id=fruit_id,
                    dish_ingredient_ids=dish_ingredient_ids,
                    rng=rng,
                )
                if alt:
                    side_ids = alt
                    day_cost = (
                        feat[main_id].cost_per_serving
                        + feat[soup_id].cost_per_serving
                        + feat[fruit_id].cost_per_serving
                        + feat[veg_id].cost_per_serving
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
                plan_days.append(PlanDay(main=main_id, sides=[], veg=veg_id, soup=soup_id, fruit=fruit_id))
                explanations.append(
                    _failed_day_explanation(
                        day_index=day,
                        reason_code=err.code,
                        message=err.message,
                        details=err.details,
                        cost=round(day_cost, 2),
                    )
                )
                continue

        # ===== success day =====
        day_obj = PlanDay(main=main_id, sides=side_ids, veg=veg_id, soup=soup_id, fruit=fruit_id)

        chosen = {
            "main": feat[main_id],
            "side1": feat[side_ids[0]],
            "side2": feat[side_ids[1]],
            "veg": feat[veg_id],
            "soup": feat[soup_id],
            "fruit": feat[fruit_id],
        }
        ctx = {
            "prev_main_meat": prev_meat,
            "prev_main_cuisine": prev_cuisine,
            "prefer_use_inventory": bool(soft.get("prefer_use_inventory", False)),
            "prefer_near_expiry": bool(soft.get("prefer_near_expiry", False)),
            "inventory_prefer_ingredient_ids": soft.get("inventory_prefer_ingredient_ids") or [],
        }
        
        
        # 最近 7 個排程日（略過 offday）
        recent_idx = []
        seen = 0
        for i in range(day - 1, -1, -1):
            if i < len(plan_days) and plan_days[i].main:
                recent_idx.append(i)
                seen += 1
                if seen >= 7:
                    break
        
        ctx.update({
            "cur_main_id": main_id,
            "cur_soup_id": soup_id,
            "cur_fruit_id": fruit_id,
            "cur_side_ids": side_ids,
            "cur_veg_id": veg_id,
        
            "recent_main_ids": [plan_days[i].main for i in recent_idx if plan_days[i].main],
            "recent_soups":    [plan_days[i].soup for i in recent_idx if plan_days[i].soup],
            "recent_fruits":   [plan_days[i].fruit for i in recent_idx if plan_days[i].fruit],
            "recent_sides":    [s for i in recent_idx for s in (plan_days[i].sides or [])],
            "recent_vegs":     [plan_days[i].veg for i in recent_idx if plan_days[i].veg],
        })

        sb = score_day(day_cost=day_cost, hard=hard, weights=weights, chosen=chosen, context=ctx)
        
        # sb.total / sb.items 在 score_day() 內已 round 過
        raw_score = float(sb.total)                 # 原始分數（越低越好）
        fitness = round(-raw_score, 2)              # ✅ 符合度（越高越好）= -sb.total
        
        # 拆解：用 sb.items 推出「加分/扣分」的總量（純粹為了展示）
        penalty_total = round(sum(v for v in sb.items.values() if v > 0), 2)     # 正數＝扣分
        bonus_total   = round(sum(-v for v in sb.items.values() if v < 0), 2)    # 負數轉正＝加分
        
        total_score += raw_score
        plan_days.append(day_obj)
        
        explanations.append({
            "day_index": day,
            "failed": False,
            "cost": round(day_cost, 2),
        
            # 原本就有的（保留）
            "score": raw_score,
            "score_breakdown": sb.items,
        
            # ✅ 新增：前端/Excel 直接用
            "score_fitness": fitness,                 # = -score
            "score_bonus_total": bonus_total,         # >= 0
            "score_penalty_total": penalty_total,     # >= 0
            "score_summary": {
                "bonus": bonus_total,
                "penalty": penalty_total,
                "raw": raw_score,
                "fitness": fitness
            },
        
            "main_meat_type": chosen["main"].meat_type,
            "inventory_used": {
                "main": chosen["main"].used_inventory_ingredients,
                "soup": chosen["soup"].used_inventory_ingredients,
                "sides": [
                    chosen["side1"].used_inventory_ingredients,
                    chosen["side2"].used_inventory_ingredients,
                ],
                "veg": chosen["veg"].used_inventory_ingredients,
            }
        })


        prev_meat = chosen["main"].meat_type
        prev_cuisine = chosen["main"].cuisine

    return plan_days, round(total_score, 2), explanations, errors
