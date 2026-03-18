# src/menu_planner/engine/planner.py
from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Tuple

from ..db.repo import Dish, SQLiteRepo
from .backtracking import fill_days_after_mains, plan_mains_beam
from .constraints import PlanDay
from .explain import build_explanations
from .features import build_dish_features
from .local_search import improve_by_local_search

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlanContext:
    start_date: date
    horizon_days: int
    active_mask: List[bool]
    hard: Dict[str, Any]
    soft: Dict[str, Any]
    weights: Dict[str, Any]
    search: Dict[str, Any]
    seed: int
    all_dishes: List[Dish]
    dishes_by_id: Dict[str, Dish]
    feat: Dict[str, Any]
    mains: List[Dish]
    sides: List[Dish]
    soups: List[Dish]
    fruits: List[Dish]


@dataclass(frozen=True)
class PlanComputation:
    final_plan: List[PlanDay]
    day_details: List[Dict[str, Any]]
    errors: List[Dict[str, Any]]
    final_score: float
    base_score: float
    incomplete_days: List[int]
    local_search_applied: bool


def _parse_start_date(cfg: Dict[str, Any]) -> date:
    s = cfg.get("start_date")
    if not s:
        return date.today()
    return datetime.strptime(s, "%Y-%m-%d").date()


def _get_active_mask(start_date: date, horizon_days: int, cfg: Dict[str, Any]) -> List[bool]:
    sch = (cfg.get("schedule") or {})
    weekdays = sch.get("weekdays") or [1, 2, 3, 4, 5]  # 預設週一到週五
    allowed = set(int(x) for x in weekdays)

    mask: List[bool] = []
    for i in range(horizon_days):
        wd = (start_date + timedelta(days=i)).isoweekday()
        mask.append(wd in allowed)
    return mask


def _resolve_seed(cfg: Dict[str, Any], start_date: date) -> int:
    """
    cfg["seed"] 可支援：
      - int: 固定 seed
      - "random": 每次都亂數
      - "time": 以時間為 seed（效果等同 random，但可讀）
      - "date": 以 start_date 為 seed（同一天重跑會一樣）
    """
    s = cfg.get("seed", 7)

    if isinstance(s, int):
        return s

    if isinstance(s, str):
        key = s.strip().lower()
        if key == "random":
            # 32-bit seed，避免過大
            return random.SystemRandom().randint(0, 2**31 - 1)
        if key == "time":
            return int(time.time()) & 0x7FFFFFFF
        if key == "date":
            return int(start_date.strftime("%Y%m%d"))

    # fallback：保留舊行為
    return 7


def _split_dishes_by_role(all_dishes: List[Dish]) -> Tuple[List[Dish], List[Dish], List[Dish], List[Dish]]:
    mains = [d for d in all_dishes if d.role == "main"]
    # veg 是「純蔬配菜」子角色，排程時仍視為 side 池的一部分。
    sides = [d for d in all_dishes if d.role in {"side", "veg"}]
    soups = [d for d in all_dishes if d.role == "soup"]
    fruits = [d for d in all_dishes if d.role == "fruit"]
    return mains, sides, soups, fruits


def _max_active_days_in_window(active_mask: List[bool], window_days: int = 30) -> int:
    if not active_mask:
        return 0

    w = max(1, int(window_days))
    best = 0
    cur = 0
    left = 0

    for right, is_active in enumerate(active_mask):
        cur += 1 if is_active else 0
        while right - left + 1 > w:
            cur -= 1 if active_mask[left] else 0
            left += 1
        if cur > best:
            best = cur
    return best


def _count_eligible_mains(mains: List[Dish], feat: Dict[str, Any], hard: Dict[str, Any]) -> int:
    excluded = set(hard.get("exclude_dish_ids", []) or [])
    allowed_meats = set(hard.get("allowed_main_meat_types", []) or [])

    count = 0
    for d in mains:
        if d.id not in feat:
            continue
        if d.id in excluded:
            continue

        meat = feat[d.id].meat_type
        if allowed_meats and meat not in allowed_meats:
            continue

        count += 1
    return count


def _auto_relax_main_repeat_limit(
    hard: Dict[str, Any],
    active_mask: List[bool],
    mains: List[Dish],
    feat: Dict[str, Any],
) -> Dict[str, Any]:
    rep = dict(hard.get("repeat_limits", {}) or {})
    cur = rep.get("max_same_main_in_30_days")
    if cur is None:
        return {}

    try:
        cur_limit = int(cur)
    except Exception:
        return {}

    eligible_mains = _count_eligible_mains(mains, feat, hard)
    if eligible_mains <= 0:
        return {}

    max_active_30 = _max_active_days_in_window(active_mask, window_days=30)
    min_needed = max(1, math.ceil(max_active_30 / eligible_mains))

    if cur_limit >= min_needed:
        return {}

    rep["max_same_main_in_30_days"] = min_needed
    hard["repeat_limits"] = rep
    return {
        "max_same_main_in_30_days": {
            "from": cur_limit,
            "to": min_needed,
            "reason": "auto_relaxed_for_feasibility",
            "eligible_mains": eligible_mains,
            "max_active_days_in_30": max_active_30,
        }
    }


def _prepare_context(db_path: str, cfg: Dict[str, Any]) -> PlanContext:
    repo = SQLiteRepo(db_path)

    start_date = _parse_start_date(cfg)
    horizon_days = int(cfg.get("horizon_days", 30))
    active_mask = _get_active_mask(start_date, horizon_days, cfg)

    hard = dict(cfg.get("hard", {}) or {})
    soft = cfg.get("soft", {}) or {}
    weights = cfg.get("weights", {}) or {}
    search = cfg.get("search", {}) or {}
    seed = _resolve_seed(cfg, start_date)
    hard["seed"] = seed

    ingredients = repo.fetch_ingredients()
    all_dishes = repo.fetch_dishes()
    dish_ingredients = repo.fetch_dish_ingredients()
    inventory = repo.fetch_inventory()
    conv = repo.fetch_unit_conversions()
    prices = repo.fetch_latest_prices(price_date=start_date.isoformat())

    dishes_by_id = {d.id: d for d in all_dishes}
    feat = build_dish_features(
        dishes=all_dishes,
        dish_ingredients=dish_ingredients,
        ingredients=ingredients,
        prices=prices,
        inventory=inventory,
        conv=conv,
        today=start_date,
    )

    mains, sides, soups, fruits = _split_dishes_by_role(all_dishes)
    auto_relaxed = _auto_relax_main_repeat_limit(
        hard=hard,
        active_mask=active_mask,
        mains=mains,
        feat=feat,
    )
    if auto_relaxed:
        hard.setdefault("_auto_relaxed", {}).update(auto_relaxed)
        logger.info("Auto-relaxed repeat limits: %s", auto_relaxed)

    logger.info(
        "Catalog counts: all=%d mains=%d sides=%d soups=%d fruits=%d",
        len(all_dishes),
        len(mains),
        len(sides),
        len(soups),
        len(fruits),
    )

    return PlanContext(
        start_date=start_date,
        horizon_days=horizon_days,
        active_mask=active_mask,
        hard=hard,
        soft=soft,
        weights=weights,
        search=search,
        seed=seed,
        all_dishes=all_dishes,
        dishes_by_id=dishes_by_id,
        feat=feat,
        mains=mains,
        sides=sides,
        soups=soups,
        fruits=fruits,
    )


def _build_offday_result(ctx: PlanContext) -> Dict[str, Any]:
    final_plan_full = [PlanDay(main="", sides=[], soup="", fruit="") for _ in range(ctx.horizon_days)]
    day_details_full = [
        {"day_index": i, "failed": False, "is_offday": True, "message": "非排程日（休息/不排）"}
        for i in range(ctx.horizon_days)
    ]

    result = build_explanations(
        start_date=ctx.start_date,
        plan_days=final_plan_full,
        dishes_by_id=ctx.dishes_by_id,
        feat=ctx.feat,
        day_scores=day_details_full,
    )
    result["errors"] = []
    result["ok"] = True
    result.setdefault("debug", {})
    result["debug"]["active_mask"] = ctx.active_mask
    result["debug"]["active_days"] = sum(1 for x in ctx.active_mask if x)
    return result


def _run_backtracking(ctx: PlanContext) -> Tuple[List[PlanDay], float, List[Dict[str, Any]], List[Dict[str, Any]]]:
    bt = (ctx.search.get("backtracking") or {})
    beam_width = int(bt.get("beam_width", 12))
    cand_limit = int((bt.get("candidate_limit_per_role") or {}).get("main", 25))

    main_ids_full = plan_mains_beam(
        horizon_days=ctx.horizon_days,
        mains=ctx.mains,
        feat=ctx.feat,
        hard=ctx.hard,
        beam_width=beam_width,
        candidate_limit=cand_limit,
        seed=ctx.seed,
        start_date=ctx.start_date,
        active_mask=ctx.active_mask,
    )

    return fill_days_after_mains(
        horizon_days=ctx.horizon_days,
        main_ids=main_ids_full,
        sides=ctx.sides,
        soups=ctx.soups,
        fruits=ctx.fruits,
        feat=ctx.feat,
        hard=ctx.hard,
        weights=ctx.weights,
        soft=ctx.soft,
        start_date=ctx.start_date,
        active_mask=ctx.active_mask,
    )


def _run_local_search(
    ctx: PlanContext,
    plan_days_full: List[PlanDay],
    base_score: float,
    base_expl: List[Dict[str, Any]],
    base_errors: List[Dict[str, Any]],
) -> PlanComputation:
    ls = (ctx.search.get("local_search") or {})
    ls_enabled = bool(ls.get("enabled", True))

    incomplete_days = [
        i
        for i, d in enumerate(plan_days_full)
        if ctx.active_mask[i] and ((not d.soup) or (not d.fruit) or (not d.sides) or (len(d.sides) != 3))
    ]

    if ls_enabled and (not incomplete_days) and (not base_errors):
        improved_plan, improved_score, improved_day_details = improve_by_local_search(
            plan_days=plan_days_full,
            mains=ctx.mains,
            sides=ctx.sides,
            soups=ctx.soups,
            fruits=ctx.fruits,
            feat=ctx.feat,
            hard=ctx.hard,
            weights=ctx.weights,
            soft=ctx.soft,
            iterations=int(ls.get("iterations", 800)),
            accept_worse_probability=float(ls.get("accept_worse_probability", 0.03)),
            seed=ctx.seed,
            start_date=ctx.start_date,
            active_mask=ctx.active_mask,
        )
        return PlanComputation(
            final_plan=improved_plan,
            day_details=improved_day_details,
            errors=base_errors,
            final_score=improved_score,
            base_score=base_score,
            incomplete_days=incomplete_days,
            local_search_applied=True,
        )

    return PlanComputation(
        final_plan=plan_days_full,
        day_details=base_expl,
        errors=base_errors,
        final_score=base_score,
        base_score=base_score,
        incomplete_days=incomplete_days,
        local_search_applied=False,
    )


def _build_debug_info(ctx: PlanContext, comp: PlanComputation) -> Dict[str, Any]:
    return {
        "seed": ctx.seed,
        "active_mask": ctx.active_mask,
        "active_days": sum(1 for x in ctx.active_mask if x),
        "failed_days": [e.get("day_index") for e in comp.errors if e.get("day_index") is not None],
        "incomplete_days": comp.incomplete_days,
        "auto_relaxed": ctx.hard.get("_auto_relaxed", {}),
        "base_fill_score": comp.base_score,
        "final_score": comp.final_score,
        "start_date": ctx.start_date.isoformat(),
        "local_search_enabled": comp.local_search_applied,
    }


def _build_result(ctx: PlanContext, comp: PlanComputation) -> Dict[str, Any]:
    result = build_explanations(
        start_date=ctx.start_date,
        plan_days=comp.final_plan,
        dishes_by_id=ctx.dishes_by_id,
        feat=ctx.feat,
        day_scores=comp.day_details,
    )
    result["errors"] = comp.errors
    result["ok"] = (len(comp.errors) == 0)
    result.setdefault("debug", {})
    result["debug"].update(_build_debug_info(ctx, comp))
    return result


def plan_month(db_path: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    ctx = _prepare_context(db_path=db_path, cfg=cfg)

    if not any(ctx.active_mask):
        return _build_offday_result(ctx)

    plan_days_full, base_score, base_expl, base_errors = _run_backtracking(ctx)
    computation = _run_local_search(ctx, plan_days_full, base_score, base_expl, base_errors)
    return _build_result(ctx, computation)
