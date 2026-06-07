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
from .constraints import check_cost_range, check_noodle_window_repeat, check_soup_window_repeat
from .roles import DEFAULT_ROLE_COUNTS
from .scoring import score_day

from .errors import PlanError

from .backtracking_selection import (
    analyze_soup_rejections,
    choose_sides_backtrack,
    choose_soup,
    choose_veg,
    pick_fruit,
)



def _side_soup_protein_limit_for_day(day_idx: int, start_date: Optional[date], hard: Dict) -> int:
    base = hard.get("side_soup_protein_limit", 2)
    overrides = hard.get("per_weekday_side_soup_protein_limit") or {}
    weekday = _weekday_for_day(day_idx, start_date)
    if isinstance(overrides, dict):
        base = overrides.get(weekday, overrides.get(str(weekday), base))
    try:
        return max(0, int(base))
    except Exception:
        return 2


def _protein_count(dish_ids: List[str], dish_has_protein: Dict[str, bool]) -> int:
    return sum(1 for did in dish_ids if did and dish_has_protein.get(did, False))


def _within_side_soup_protein_limit(side_ids: List[str], soup_ids: List[str], dish_has_protein: Dict[str, bool], limit: int) -> bool:
    return _protein_count(list(side_ids) + list(soup_ids), dish_has_protein) <= limit


def _protein_limit_error(day: int, total: int, limit: int, side_ids: List[str], soup_ids: List[str], dish_has_protein: Dict[str, bool]) -> PlanError:
    protein_items = [did for did in list(side_ids) + list(soup_ids) if did and dish_has_protein.get(did, False)]
    return PlanError(
        code="SIDE_SOUP_PROTEIN_LIMIT_EXCEEDED",
        day_index=day,
        message=f"第 {day+1} 天配菜與湯品含蛋白質菜色共 {total} 道，超過上限 {limit} 道。",
        details={
            "side_soup_protein_count": total,
            "side_soup_protein_limit": limit,
            "protein_items": protein_items,
            "sides": side_ids,
            "soups": soup_ids,
            "hint": "可調高配菜＋湯品含蛋白質上限、依週幾覆寫上限，或增加不含蛋白質欄位的配菜/湯品候選。",
        },
    )


def _prep_minutes_for_day(day_idx: int, start_date: Optional[date], hard: Dict) -> int:
    base = hard.get("prep_time_limit_minutes", 90)
    overrides = hard.get("per_weekday_prep_time_limit_minutes") or {}
    weekday = _weekday_for_day(day_idx, start_date)
    if isinstance(overrides, dict):
        base = overrides.get(weekday, overrides.get(str(weekday), base))
    try:
        return max(0, int(base))
    except Exception:
        return 90


def _dish_prep_minutes(dish: Optional[Dish]) -> int:
    try:
        return max(0, int(getattr(dish, "prep_minutes", 0) or 0))
    except Exception:
        return 0


def _prep_total(dish_ids: List[str], dish_by_id: Dict[str, Dish]) -> int:
    return sum(_dish_prep_minutes(dish_by_id.get(did)) for did in dish_ids if did)


def _filter_pool_by_remaining_prep(pool: List[Dish], current_ids: List[str], dish_by_id: Dict[str, Dish], limit: int) -> List[Dish]:
    current = _prep_total(current_ids, dish_by_id)
    remaining = limit - current
    return [d for d in pool if _dish_prep_minutes(d) <= remaining]


def _all_day_ids(main_ids: List[str], noodle_ids: List[str], soup_ids: List[str], fruit_ids: List[str], side_ids: List[str], veg_ids: List[str]) -> List[str]:
    return [x for x in (list(main_ids) + list(noodle_ids) + list(soup_ids) + list(fruit_ids) + list(side_ids) + list(veg_ids)) if x]


def _prep_limit_error(day: int, total: int, limit: int, selected_ids: List[str], dish_by_id: Dict[str, Dish]) -> PlanError:
    breakdown = {did: _dish_prep_minutes(dish_by_id.get(did)) for did in selected_ids if did}
    return PlanError(
        code="PREP_TIME_LIMIT_EXCEEDED",
        day_index=day,
        message=f"第 {day+1} 天備菜時間總和 {total} 分鐘超過備菜時間上限 {limit} 分鐘。",
        details={
            "prep_minutes_total": total,
            "prep_minutes_limit": limit,
            "items": selected_ids,
            "prep_breakdown": breakdown,
            "hint": "可調高每日備菜時間上限、依週幾覆寫上限、降低菜色備菜時間，或增加短備菜時間候選。",
        },
    )


def _weekday_for_day(day_idx: int, start_date: Optional[date]) -> int:
    if start_date is not None:
        return (start_date + timedelta(days=day_idx)).isoweekday()
    return (day_idx % 7) + 1


def _normalize_weekday_set(value) -> Set[int]:
    if value is None:
        return {1, 2, 3, 4, 5, 6, 7}
    if not isinstance(value, list):
        return {1, 2, 3, 4, 5, 6, 7}
    out: Set[int] = set()
    for x in value:
        try:
            wd = int(x)
        except Exception:
            continue
        if 1 <= wd <= 7:
            out.add(wd)
    return out or {1, 2, 3, 4, 5, 6, 7}


def _dish_allowed_on_day(dish: Dish, day_idx: int, start_date: Optional[date], hard: Dict) -> bool:
    rules = (hard.get("dish_allowed_weekdays") or {}) if isinstance(hard, dict) else {}
    allowed = _normalize_weekday_set(rules.get(dish.id))
    return _weekday_for_day(day_idx, start_date) in allowed


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
    role_counts_by_day: Optional[List[Dict[str, int]]] = None,
) -> List[str]:
    rng = random.Random(seed)

    # 候選先隨機打散，再用成本/庫存等排序
    main_by_id = {d.id: d for d in mains}
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

        counts = (role_counts_by_day[day] if role_counts_by_day and day < len(role_counts_by_day) else DEFAULT_ROLE_COUNTS)
        is_active = (True if use_mask is None else bool(use_mask[day])) and int(counts.get("main", 1) or 0) > 0

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
                dish = main_by_id.get(did)
                if dish is not None and not _dish_allowed_on_day(dish, day, start_date, hard):
                    continue
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


# Backward-compatible aliases for tests/internal imports.
_pick_fruit = pick_fruit
_choose_soup = choose_soup
_analyze_soup_rejections = analyze_soup_rejections
_choose_sides_backtrack = choose_sides_backtrack
_choose_veg = choose_veg

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
    dish_has_protein: Optional[Dict[str, bool]] = None,
    start_date: Optional[date] = None,          # ✅ 新增（可選）
    active_mask: Optional[List[bool]] = None,   # ✅ 新增（可選）
    role_counts_by_day: Optional[List[Dict[str, int]]] = None,
    noodles: Optional[List[Dish]] = None,
    mains: Optional[List[Dish]] = None,
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
    max_noodle_7 = int(rep.get("max_same_noodle_in_7_days", 1))
    max_noodle_30 = int(rep.get("max_same_noodle_in_30_days", 2))

    cr = (hard.get("cost_range_per_person_per_day") or {})
    cost_min = float(cr.get("min", 0))
    cost_max = float(cr.get("max", 10**18))

    side_pool0  = [d for d in sides  if d.id in feat]
    veg_pool0   = [d for d in vegs   if d.id in feat]
    soup_pool0  = [d for d in soups  if d.id in feat]
    fruit_pool0 = [d for d in fruits if d.id in feat]
    noodle_pool0 = [d for d in (noodles or []) if d.id in feat]
    main_pool0 = [d for d in (mains or []) if d.id in feat]
    dish_by_id = {d.id: d for d in (list(mains or []) + list(noodles or []) + list(sides or []) + list(vegs or []) + list(soups or []) + list(fruits or []))}
    dish_has_protein = dish_has_protein or {}
    
    print("usable sides (in feat):", len(side_pool0), "/", len(sides))
    print("usable vegs  (in feat):", len(veg_pool0), "/", len(vegs))
    print("usable soups (in feat):", len(soup_pool0), "/", len(soups))
    print("usable fruits(in feat):", len(fruit_pool0), "/", len(fruits))
    print("usable noodles(in feat):", len(noodle_pool0), "/", len(noodles or []))
    print("usable mains (in feat):", len(main_pool0), "/", len(mains or []))

    def choose_distinct_from_pool(pool: List[Dish], count: int, selected: List[str]) -> List[str]:
        if count <= 0:
            return []
        chosen: List[str] = []
        blocked = set(x for x in selected if x)
        for d in pool:
            if d.id in blocked:
                continue
            chosen.append(d.id)
            blocked.add(d.id)
            if len(chosen) >= count:
                break
        return chosen

    def choose_noodles_from_pool(pool: List[Dish], count: int, selected: List[str], day_idx: int) -> List[str]:
        if count <= 0:
            return []
        chosen: List[str] = []
        blocked = set(x for x in selected if x)
        for d in pool:
            if d.id in blocked:
                continue
            candidate = chosen + [d.id]
            if not check_noodle_window_repeat(day_idx, candidate, plan_days, max_noodle_7, window_days=7):
                continue
            if not check_noodle_window_repeat(day_idx, candidate, plan_days, max_noodle_30, window_days=30):
                continue
            chosen.append(d.id)
            blocked.add(d.id)
            if len(chosen) >= count:
                break
        return chosen

    for day in range(horizon_days):
        counts = (role_counts_by_day[day] if role_counts_by_day and day < len(role_counts_by_day) else DEFAULT_ROLE_COUNTS)
        main_count = int(counts.get("main", 1) or 0)
        noodle_count = int(counts.get("noodle", 0) or 0)
        side_count = int(counts.get("side", 2) or 0)
        veg_count = int(counts.get("veg", 1) or 0)
        soup_count = int(counts.get("soup", 1) or 0)
        fruit_count = int(counts.get("fruit", 1) or 0)
        prep_limit = _prep_minutes_for_day(day, start_date, hard)
        protein_limit = _side_soup_protein_limit_for_day(day, start_date, hard)
        schedule_active = True if active_mask is None or day >= len(active_mask) else bool(active_mask[day])
        if not schedule_active:
            main_count = noodle_count = side_count = veg_count = soup_count = fruit_count = 0
        main_id = main_ids[day] if main_count > 0 else ""
        if not any([main_count, noodle_count, side_count, veg_count, soup_count, fruit_count]):
            plan_days.append(PlanDay(main="", sides=[], veg="", soup="", fruit="", noodle=""))
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
        
        # 只拿可用候選（在 feat 裡），並套用單一道菜允許供應週幾。
        main_pool = [d for d in main_pool0 if _dish_allowed_on_day(d, day, start_date, hard)]
        noodle_pool = [d for d in noodle_pool0 if _dish_allowed_on_day(d, day, start_date, hard)]
        fruit_pool = [d for d in fruit_pool0 if _dish_allowed_on_day(d, day, start_date, hard)]
        soup_pool  = [d for d in soup_pool0 if _dish_allowed_on_day(d, day, start_date, hard)]
        side_pool  = [d for d in side_pool0 if _dish_allowed_on_day(d, day, start_date, hard)]
        veg_pool   = [d for d in veg_pool0 if _dish_allowed_on_day(d, day, start_date, hard)]
        
        rng.shuffle(main_pool)
        rng.shuffle(noodle_pool)
        rng.shuffle(fruit_pool)
        rng.shuffle(soup_pool)
        rng.shuffle(side_pool)
        rng.shuffle(veg_pool)
        
        main_extra_ids = choose_distinct_from_pool(main_pool, max(0, main_count - (1 if main_id else 0)), [main_id])
        main_ids_today = ([main_id] if main_id else []) + main_extra_ids
        if main_count > 0 and len(main_ids_today) < main_count:
            err = PlanError(
                code="MAIN_NO_SOLUTION",
                day_index=day,
                message=f"第 {day+1} 天找不到足夠的主菜。",
                details={"candidate_count": len(main_pool), "requested_count": main_count, "selected_count": len(main_ids_today)},
            )
            errors.append(err.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup="", fruit="", noodle="", mains=main_ids_today))
            explanations.append(_failed_day_explanation(day_index=day, reason_code=err.code, message=err.message, details=err.details))
            continue

        selected_for_prep = list(main_ids_today)
        selected_prep = _prep_total(selected_for_prep, dish_by_id)
        if selected_prep > prep_limit:
            err = _prep_limit_error(day, selected_prep, prep_limit, selected_for_prep, dish_by_id)
            errors.append(err.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup="", fruit="", noodle="", mains=main_ids_today))
            explanations.append(_failed_day_explanation(day_index=day, reason_code=err.code, message=err.message, details=err.details))
            continue

        noodle_ids = []
        noodle_id = ""
        if noodle_count > 0:
            noodle_pool_limited = _filter_pool_by_remaining_prep(noodle_pool, main_ids_today, dish_by_id, prep_limit)
            noodle_ids = choose_noodles_from_pool(noodle_pool_limited, noodle_count, main_ids_today, day)
            noodle_id = noodle_ids[0] if noodle_ids else ""
            if len(noodle_ids) < noodle_count:
                err = PlanError(
                    code="NOODLE_NO_SOLUTION",
                    day_index=day,
                    message=f"第 {day+1} 天找不到符合限制的麵食。",
                    details={
                        "candidate_count": len(noodle_pool),
                        "candidate_count_after_prep_limit": len(noodle_pool_limited),
                        "prep_minutes_limit": prep_limit,
                        "requested_count": noodle_count,
                        "selected_count": len(noodle_ids),
                        "max_same_noodle_in_7_days": max_noodle_7,
                        "max_same_noodle_in_30_days": max_noodle_30,
                        "hint": "可放寬麵食 7 天或 30 天重複限制，或增加麵食候選。",
                    },
                )
                errors.append(err.to_dict())
                plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup="", fruit="", noodle="", mains=main_ids_today, noodles=noodle_ids))
                explanations.append(_failed_day_explanation(day_index=day, reason_code=err.code, message=err.message, details=err.details))
                continue

        # ===== fruit（若整個水果類別空，這屬於「系統性缺資料」，建議仍可 raise）=====
        # 你想「連水果都缺也繼續排」也行，但通常代表資料集不完整
        fruit_ids = []
        if fruit_count <= 0:
            fruit_id = ""
        else:
            try:
                #fruit_id = pick_fruit(fruits, day, feat)
                #fruit_id = pick_fruit(fruit_pool, day, feat)
                fruit_id = pick_fruit(
                    _filter_pool_by_remaining_prep(fruit_pool, main_ids_today + noodle_ids, dish_by_id, prep_limit),
                    day,
                    plan_days,
                    feat,
                    hard,
                    dish_ingredient_ids=dish_ingredient_ids,
                    selected_dish_ids=main_ids_today + noodle_ids,
                )
                fruit_ids = [fruit_id] if fruit_id else []
                if fruit_id and fruit_count > 1:
                    fruit_ids += choose_distinct_from_pool(fruit_pool, fruit_count - 1, main_ids_today + noodle_ids + fruit_ids)
                fruit_id = fruit_ids[0] if fruit_ids else ""
                if len(fruit_ids) < fruit_count:
                    raise PlanError(
                        code="FRUIT_NO_SOLUTION",
                        day_index=day,
                        message=f"第 {day+1} 天找不到足夠的水果。",
                        details={"candidate_count": len(fruit_pool), "requested_count": fruit_count, "selected_count": len(fruit_ids)},
                    )
            except PlanError as e:
                # 系統性缺水果：仍可回傳 errors + placeholder 後繼續
                errors.append(e.to_dict())
                plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup="", fruit="", noodle=noodle_id, mains=main_ids_today, noodles=noodle_ids, fruits=fruit_ids))
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
        #soup_id = choose_soup(day, soups, plan_days, feat, hard)
        #soup_id  = choose_soup(day, soup_pool, plan_days, feat, hard)
        soup_id = ""
        if soup_count > 0:
            soup_id = choose_soup(
                day,
                _filter_pool_by_remaining_prep(soup_pool, main_ids_today + noodle_ids + fruit_ids, dish_by_id, prep_limit),
                plan_days,
                feat,
                hard,
                main_id=main_id,
                dish_ingredient_ids=dish_ingredient_ids,
                dish_has_protein=dish_has_protein,
                selected_soup_ids=[],
                side_soup_protein_limit=protein_limit,
                rng=rng,
            )
            soup_ids = [soup_id] if soup_id else []
            if soup_id and soup_count > 1:
                for extra_id in choose_distinct_from_pool(soup_pool, soup_count - 1, main_ids_today + noodle_ids + soup_ids + fruit_ids):
                    if _within_side_soup_protein_limit([], soup_ids + [extra_id], dish_has_protein, protein_limit):
                        soup_ids.append(extra_id)
            soup_id = soup_ids[0] if soup_ids else ""
        else:
            soup_ids = []
        if soup_count > 0 and len(soup_ids) < soup_count:
            soup_stats = analyze_soup_rejections(
                day_idx=day,
                soups=soup_pool,
                plan_days=plan_days,
                feat=feat,
                hard=hard,
                main_id=main_id,
                dish_ingredient_ids=dish_ingredient_ids,
            )
            err = PlanError(
                code="SOUP_NO_SOLUTION",
                day_index=day,
                message=f"第 {day+1} 天找不到符合重複限制的湯。",
                details={
                    "max_same_soup_in_7_days": max_soup_7,
                    "max_same_ingredient_in_window_days": soup_stats["max_same_ingredient_in_window_days"],
                    "ingredient_repeat_window_days": soup_stats["ingredient_repeat_window_days"],
                    "candidate_count": soup_stats["candidate_count"],
                    "feasible_count": soup_stats["feasible_count"],
                    "blocked_by_soup_repeat": soup_stats["blocked_by_soup_repeat"],
                    "blocked_by_ingredient_repeat": soup_stats["blocked_by_ingredient_repeat"],
                    "hint": f"可放寬湯品 7 天重複，或放寬食材 {soup_stats['ingredient_repeat_window_days']} 天重複限制，或增加湯品候選。",
                }
            )
            errors.append(err.to_dict())

            # 湯無解時，仍嘗試保留可排到的配菜/蔬菜/水果，湯留空給使用者後續調整
            side_ids = choose_sides_backtrack(
                day,
                side_pool,
                plan_days,
                feat,
                hard,
                main_id=main_id,
                soup_id="",
                fruit_id=fruit_id,
                dish_ingredient_ids=dish_ingredient_ids,
                dish_has_protein=dish_has_protein,
                soup_ids=soup_ids,
                side_soup_protein_limit=protein_limit,
                rng=rng,
                pick_count=side_count,
            ) or []

            veg_id = ""
            if side_ids:
                veg_id = choose_veg(
                    day,
                    veg_pool,
                    plan_days,
                    feat,
                    hard,
                    selected_dish_ids=[x for x in [main_id, noodle_id, fruit_id] if x] + list(side_ids),
                    dish_ingredient_ids=dish_ingredient_ids,
                    rng=rng,
                ) or ""

            plan_days.append(PlanDay(main=main_id, sides=side_ids, veg=veg_id, soup="", fruit=fruit_id, noodle=noodle_id, mains=main_ids_today, noodles=noodle_ids, vegs=[veg_id] if veg_id else [], fruits=fruit_ids))
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
        #side_ids = choose_sides_backtrack(day, sides, plan_days, feat, hard)
        #side_ids = choose_sides_backtrack(day, side_pool, plan_days, feat, hard)
        side_ids = []
        side_pool_prep_limited = _filter_pool_by_remaining_prep(
            side_pool,
            main_ids_today + noodle_ids + soup_ids + fruit_ids,
            dish_by_id,
            prep_limit,
        )
        if side_count > 0:
            side_ids = choose_sides_backtrack(
                day,
                side_pool_prep_limited,
                plan_days,
                feat,
                hard,
                main_id=main_id,
                soup_id=soup_id,
                fruit_id=fruit_id,
                dish_ingredient_ids=dish_ingredient_ids,
                dish_has_protein=dish_has_protein,
                soup_ids=soup_ids,
                side_soup_protein_limit=protein_limit,
                rng=rng,
                pick_count=side_count,
            )
        if side_count > 0 and not side_ids:
            side_candidates = [d.id for d in sides if d.id in feat]
            if len(side_pool_prep_limited) < side_count:
                current_ids = _all_day_ids(main_ids_today, noodle_ids, soup_ids, fruit_ids, [], [])
                err = _prep_limit_error(day, _prep_total(current_ids, dish_by_id), prep_limit, current_ids, dish_by_id)
                err.message = f"第 {day+1} 天找不到符合備菜時間上限的指定數量配菜。"
                err.details["candidate_count"] = len(side_candidates)
                err.details["candidate_count_after_prep_limit"] = len(side_pool_prep_limited)
                err.details["requested_side_count"] = side_count
            else:
                err = PlanError(
                    code="SIDE_NO_SOLUTION",
                    day_index=day,
                    message=f"第 {day+1} 天找不到符合重複限制的指定數量配菜。",
                    details={
                        "max_same_side_in_7_days": max_side_7,
                        "candidate_count": len(side_candidates),
                        "hint": "可放寬配菜 7 天重複限制、調高備菜時間上限，或增加配菜候選。"
                    }
                )
            errors.append(err.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup=soup_id, fruit=fruit_id, noodle=noodle_id, mains=main_ids_today, noodles=noodle_ids, soups=[soup_id] if soup_id else [], fruits=fruit_ids))
            explanations.append(
                _failed_day_explanation(
                    day_index=day,
                    reason_code=err.code,
                    message=err.message,
                    details=err.details,
                )
            )
            continue

        side_soup_protein_total = _protein_count(list(side_ids) + list(soup_ids), dish_has_protein)
        if not _within_side_soup_protein_limit(side_ids, soup_ids, dish_has_protein, protein_limit):
            err = _protein_limit_error(day, side_soup_protein_total, protein_limit, side_ids, soup_ids, dish_has_protein)
            errors.append(err.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup=soup_id, fruit=fruit_id, noodle=noodle_id, mains=main_ids_today, noodles=noodle_ids, soups=soup_ids, fruits=fruit_ids))
            explanations.append(_failed_day_explanation(day_index=day, reason_code=err.code, message=err.message, details=err.details))
            continue

        veg_id = ""
        veg_ids = []
        if veg_count > 0:
            veg_id = choose_veg(
                day,
                _filter_pool_by_remaining_prep(veg_pool, main_ids_today + noodle_ids + soup_ids + fruit_ids + list(side_ids), dish_by_id, prep_limit),
                plan_days,
                feat,
                hard,
                selected_dish_ids=main_ids_today + noodle_ids + soup_ids + fruit_ids + list(side_ids),
                dish_ingredient_ids=dish_ingredient_ids,
                rng=rng,
            )
            veg_ids = [veg_id] if veg_id else []
            if veg_id and veg_count > 1:
                veg_ids += choose_distinct_from_pool(veg_pool, veg_count - 1, main_ids_today + noodle_ids + soup_ids + fruit_ids + list(side_ids) + veg_ids)
            veg_id = veg_ids[0] if veg_ids else ""
        if veg_count > 0 and len(veg_ids) < veg_count:
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
            plan_days.append(PlanDay(main=main_id, sides=side_ids, veg="", soup=soup_id, fruit=fruit_id, noodle=noodle_id, mains=main_ids_today, noodles=noodle_ids, soups=[soup_id] if soup_id else [], fruits=fruit_ids))
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
            sum(feat[x].cost_per_serving for x in main_ids_today if x in feat)
            + sum(feat[x].cost_per_serving for x in noodle_ids if x in feat)
            + sum(feat[x].cost_per_serving for x in soup_ids if x in feat)
            + sum(feat[x].cost_per_serving for x in fruit_ids if x in feat)
            + sum(feat[x].cost_per_serving for x in veg_ids if x in feat)
            + sum(feat[s].cost_per_serving for s in side_ids)
        )

        selected_ids_today = _all_day_ids(main_ids_today, noodle_ids, soup_ids, fruit_ids, side_ids, veg_ids)
        prep_total = _prep_total(selected_ids_today, dish_by_id)
        if prep_total > prep_limit:
            err = _prep_limit_error(day, prep_total, prep_limit, selected_ids_today, dish_by_id)
            errors.append(err.to_dict())
            plan_days.append(PlanDay(main=main_id, sides=[], veg="", soup=soup_id, fruit=fruit_id, noodle=noodle_id, mains=main_ids_today, noodles=noodle_ids, soups=soup_ids, fruits=fruit_ids))
            explanations.append(_failed_day_explanation(day_index=day, reason_code=err.code, message=err.message, details=err.details, cost=round(day_cost, 2)))
            continue

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
                if not _within_side_soup_protein_limit(side_ids, [sid], dish_has_protein, protein_limit):
                    continue
                test_cost = (
                    feat[main_id].cost_per_serving
                    + feat[sid].cost_per_serving
                    + (feat[fruit_id].cost_per_serving if fruit_id else 0)
                    + (feat[veg_id].cost_per_serving if veg_id else 0)
                    + sum(feat[s].cost_per_serving for s in side_ids)
                )
                if check_cost_range(test_cost, hard):
                    soup_id = sid
                    day_cost = test_cost
                    ok = True
                    break

            # 重試配菜（改用另一組）
            if not ok:
                #alt = choose_sides_backtrack(day, sides[::-1], plan_days, feat, hard)  # 反向試一次
                alt_pool = side_pool[:]
                rng.shuffle(alt_pool)
                #alt = choose_sides_backtrack(day, alt_pool, plan_days, feat, hard)
                alt = choose_sides_backtrack(
                    day,
                    alt_pool,
                    plan_days,
                    feat,
                    hard,
                    main_id=main_id,
                    soup_id=soup_id,
                    fruit_id=fruit_id,
                    dish_ingredient_ids=dish_ingredient_ids,
                    dish_has_protein=dish_has_protein,
                    soup_ids=[soup_id] if soup_id else [],
                    side_soup_protein_limit=protein_limit,
                    rng=rng,
                )
                if alt:
                    side_ids = alt
                    day_cost = (
                        feat[main_id].cost_per_serving
                        + (feat[soup_id].cost_per_serving if soup_id else 0)
                        + (feat[fruit_id].cost_per_serving if fruit_id else 0)
                        + (feat[veg_id].cost_per_serving if veg_id else 0)
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
                            "soup": round((feat[soup_id].cost_per_serving if soup_id else 0), 2),
                            "fruit": round((feat[fruit_id].cost_per_serving if fruit_id else 0), 2),
                            "sides": [round(feat[s].cost_per_serving, 2) for s in side_ids],
                        },
                        "hint": "可提高成本上限、增加低成本候選、或放寬湯/配菜重複限制以擴大可替換組合。"
                    }
                )
                errors.append(err.to_dict())
                # placeholder：主菜/湯/果保留，配菜清空（代表當天未完成）
                plan_days.append(PlanDay(main=main_id, sides=[], veg=veg_id, soup=soup_id, fruit=fruit_id, noodle=noodle_id, mains=main_ids_today, noodles=noodle_ids, vegs=[veg_id] if veg_id else [], soups=[soup_id] if soup_id else [], fruits=fruit_ids))
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
        day_obj = PlanDay(
            main=main_id,
            sides=side_ids,
            veg=veg_id,
            soup=soup_id,
            fruit=fruit_id,
            noodle=noodle_id,
            mains=main_ids_today,
            noodles=noodle_ids,
            vegs=veg_ids,
            soups=soup_ids,
            fruits=fruit_ids,
        )

        chosen = {
            "main": feat[main_id] if main_id else feat[noodle_id],
            **({"noodle": feat[noodle_id]} if noodle_id else {}),
            "side1": feat[side_ids[0]] if len(side_ids) > 0 else (feat[main_id] if main_id else feat[noodle_id]),
            "side2": feat[side_ids[1]] if len(side_ids) > 1 else (feat[side_ids[0]] if side_ids else (feat[main_id] if main_id else feat[noodle_id])),
            "veg": feat[veg_id] if veg_id else (feat[main_id] if main_id else feat[noodle_id]),
            "soup": feat[soup_id] if soup_id else (feat[main_id] if main_id else feat[noodle_id]),
            "fruit": feat[fruit_id] if fruit_id else (feat[main_id] if main_id else feat[noodle_id]),
        }
        ctx = {
            "prev_main_meat": prev_meat,
            "prev_main_cuisine": prev_cuisine,
            "prefer_use_inventory": bool(soft.get("prefer_use_inventory", False)),
            "prefer_near_expiry": bool(soft.get("prefer_near_expiry", False)),
            "inventory_prefer_ingredient_ids": soft.get("inventory_prefer_ingredient_ids") or [],
            "plan_date": (start_date + timedelta(days=day)).isoformat(),
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
            "cur_noodle_id": noodle_id,
            "cur_soup_id": soup_id,
            "cur_fruit_id": fruit_id,
            "cur_side_ids": side_ids,
            "cur_veg_id": veg_id,
        
            "recent_main_ids": [m for i in recent_idx for m in (getattr(plan_days[i], "mains", None) or ([plan_days[i].main] if plan_days[i].main else []))],
            "recent_soups":    [s for i in recent_idx for s in (getattr(plan_days[i], "soups", None) or ([plan_days[i].soup] if plan_days[i].soup else []))],
            "recent_fruits":   [f for i in recent_idx for f in (getattr(plan_days[i], "fruits", None) or ([plan_days[i].fruit] if plan_days[i].fruit else []))],
            "recent_sides":    [s for i in recent_idx for s in (plan_days[i].sides or [])],
            "recent_vegs":     [v for i in recent_idx for v in (getattr(plan_days[i], "vegs", None) or ([plan_days[i].veg] if plan_days[i].veg else []))],
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
            "prep_minutes_total": prep_total,
            "prep_minutes_limit": prep_limit,
            "side_soup_protein_count": side_soup_protein_total,
            "side_soup_protein_limit": protein_limit,
        
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


        prev_meat = chosen["main"].meat_type if main_id else prev_meat
        prev_cuisine = chosen["main"].cuisine if main_id else prev_cuisine

    return plan_days, round(total_score, 2), explanations, errors
