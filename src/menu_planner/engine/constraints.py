# src/menu_planner/engine/constraints.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from datetime import date, timedelta   # ✅ 改這行


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
        
def _fixed_main_allowed_meats(
    day_idx: int,
    hard: Dict,
    start_date: Optional[date],
) -> Optional[set]:
    """
    hard.fixed_main_meat_by_weekday:
      - key: ISO weekday (1..7) 可用 int 或 str
      - value: str 或 list[str]
    """
    fixed = (hard.get("fixed_main_meat_by_weekday") or {})
    if not fixed or start_date is None:
        return None

    wd = (start_date + timedelta(days=day_idx)).isoweekday()  # 1..7
    rule = fixed.get(wd) or fixed.get(str(wd))
    if not rule:
        return None

    if isinstance(rule, str):
        r = rule.strip()
        return {r} if r else None

    if isinstance(rule, list):
        s = {str(x).strip() for x in rule if x is not None and str(x).strip()}
        return s if s else None

    return None

def _as_single_meat(rule) -> Optional[str]:
    """只在規則是單一肉類時回傳字串；多選（list>1）就回傳 None（不做保留）。"""
    if isinstance(rule, str):
        r = rule.strip()
        return r if r else None
    if isinstance(rule, list):
        xs = [str(x).strip() for x in rule if x is not None and str(x).strip()]
        return xs[0] if len(xs) == 1 else None
    return None


def _reserve_future_fixed_slots_in_same_iso_week(
    *,
    day_idx: int,
    start_date: Optional[date],
    hard: Dict,
    target_meat: str,
) -> int:
    """
    回傳：在「同一個 ISO 週」中，位於今天之後、且固定必須是 target_meat 的天數（用來保留週配額）。
    只處理固定規則是「單一肉類」的情況（例如 {"3":["noodles"]} 或 {"3":"noodles"}）。
    """
    if start_date is None:
        return 0

    fixed = (hard.get("fixed_main_meat_by_weekday") or {})
    if not fixed:
        return 0

    today = start_date + timedelta(days=day_idx)
    week_start = today - timedelta(days=today.isoweekday() - 1)  # 週一

    reserve = 0
    for k, rule in fixed.items():
        try:
            wd = int(k)  # 1..7
        except Exception:
            continue

        mt = _as_single_meat(rule)
        if not mt or mt != target_meat:
            continue

        fixed_date = week_start + timedelta(days=wd - 1)
        fixed_idx = (fixed_date - start_date).days

        # 只保留「今天之後」的固定日（今天本身不算保留，因為你現在就在選今天）
        if fixed_idx > day_idx:
            reserve += 1

    return reserve

def check_main_hard(
    day_idx: int,
    main_id: str,
    main_meat_type: Optional[str],
    plan_main_ids: List[str],
    plan_main_meats: List[Optional[str]],
    weekly_meat_counts: Dict[int, Dict[str, int]],
    hard: Dict,
    week_key: Optional[int] = None,
    start_date: Optional[date] = None,   # ✅ 新增
) -> bool:
    # ✅ 1) 固定星期幾的主菜肉類（若有設定就必須符合）
    fixed_allowed = _fixed_main_allowed_meats(day_idx, hard, start_date)
    if fixed_allowed is not None:
        if (main_meat_type or "") not in fixed_allowed:
            return False

    # ✅ 2) 原本 allowed_main_meat_types
    allowed = set(hard.get("allowed_main_meat_types", []))
    if allowed and (main_meat_type not in allowed):
        return False

    # ✅ 3) 連續同肉
    if hard.get("no_consecutive_same_main_meat", False):
        if day_idx > 0 and plan_main_meats and plan_main_meats[-1] == main_meat_type:
            return False

    # ✅ 4) 週配額
    weekly_max = hard.get("weekly_max_main_meat", {}) or {}
    w = week_key if week_key is not None else (day_idx // 7)

    counts = weekly_meat_counts.get(w, {})
    if main_meat_type:
        max_allowed = weekly_max.get(main_meat_type)
        if max_allowed is not None:
            cur = counts.get(main_meat_type, 0)
    
            # ✅ 關鍵：保留同週未來固定日的名額（避免週三固定 noodles 卻被週一先用掉）
            reserve = _reserve_future_fixed_slots_in_same_iso_week(
                day_idx=day_idx,
                start_date=start_date,
                hard=hard,
                target_meat=main_meat_type,
            )
    
            if cur + 1 + reserve > int(max_allowed):
                return False

    # ✅ 5) 30 天內同主菜重複（rolling window：最近 30 天）
    rep = hard.get("repeat_limits", {}) or {}
    max_same_main = rep.get("max_same_main_in_30_days")
    if max_same_main is not None:
        window_days = 30
        start = max(0, day_idx - window_days)  # 取「前 30 天」：day_idx-30 ~ day_idx-1
        used = 0
        # plan_main_ids 內 offday 會是 ""，不計入
        for mid in plan_main_ids[start:day_idx]:
            if mid and mid == main_id:
                used += 1
        if used + 1 > int(max_same_main):
            return False

    # ✅ 6) exclude dish
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
