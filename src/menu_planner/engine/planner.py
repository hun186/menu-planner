# src/menu_planner/engine/planner.py
from __future__ import annotations

from datetime import date, datetime
from datetime import timedelta
from typing import Dict, Any, List, Tuple

from ..db.repo import SQLiteRepo, Dish
from .features import build_dish_features
from .backtracking import plan_mains_beam, fill_days_after_mains
from .local_search import improve_by_local_search, compute_total_score
from .explain import build_explanations
from .constraints import PlanDay


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

def plan_month(db_path: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    repo = SQLiteRepo(db_path)

    start_date = _parse_start_date(cfg)
    horizon_days = int(cfg.get("horizon_days", 30))

    active_mask = _get_active_mask(start_date, horizon_days, cfg)

    hard = cfg.get("hard", {}) or {}
    soft = cfg.get("soft", {}) or {}
    weights = cfg.get("weights", {}) or {}
    search = cfg.get("search", {}) or {}

    # load catalog
    ingredients = repo.fetch_ingredients()
    all_dishes = repo.fetch_dishes()
    dish_ingredients = repo.fetch_dish_ingredients()
    inventory = repo.fetch_inventory()
    conv = repo.fetch_unit_conversions()
    prices = repo.fetch_latest_prices(price_date=start_date.isoformat())

    dishes_by_id = {d.id: d for d in all_dishes}

    # build features
    feat = build_dish_features(
        dishes=all_dishes,
        dish_ingredients=dish_ingredients,
        ingredients=ingredients,
        prices=prices,
        inventory=inventory,
        conv=conv,
        today=start_date,
    )

    mains = [d for d in all_dishes if d.role == "main"]
    sides = [d for d in all_dishes if d.role == "side"]
    soups = [d for d in all_dishes if d.role == "soup"]
    fruits = [d for d in all_dishes if d.role == "fruit"]

    # ✅ 若全都不排（weekdays 空或全不選），直接回傳全休息日
    if not any(active_mask):
        final_plan_full = [PlanDay(main="", sides=[], soup="", fruit="") for _ in range(horizon_days)]
        day_details_full = [{
            "day_index": i,
            "failed": False,
            "is_offday": True,
            "message": "非排程日（休息/不排）"
        } for i in range(horizon_days)]

        result = build_explanations(
            start_date=start_date,
            plan_days=final_plan_full,
            dishes_by_id=dishes_by_id,
            feat=feat,
            day_scores=day_details_full
        )
        result["errors"] = []
        result["ok"] = True
        result.setdefault("debug", {})
        result["debug"]["active_mask"] = active_mask
        result["debug"]["active_days"] = sum(1 for x in active_mask if x)
        return result

    # beam params
    bt = (search.get("backtracking") or {})
    beam_width = int(bt.get("beam_width", 12))
    cand_limit = int((bt.get("candidate_limit_per_role") or {}).get("main", 25))

    # ✅ 關鍵：horizon_days 仍用完整天數，並把 active_mask / start_date 往下傳
    main_ids_full = plan_mains_beam(
        horizon_days=horizon_days,
        mains=mains,
        feat=feat,
        hard=hard,
        beam_width=beam_width,
        candidate_limit=cand_limit,
        seed=7,
        start_date=start_date,
        active_mask=active_mask,
    )

    plan_days_full, base_score, base_expl, base_errors = fill_days_after_mains(
        horizon_days=horizon_days,
        main_ids=main_ids_full,
        sides=sides,
        soups=soups,
        fruits=fruits,
        feat=feat,
        hard=hard,
        weights=weights,
        soft=soft,
        start_date=start_date,
        active_mask=active_mask,
    )

    # local search（只在「實際排的日」都完整且無錯時才做）
    ls = (search.get("local_search") or {})
    ls_enabled = bool(ls.get("enabled", True))

    incomplete_days = [
        i for i, d in enumerate(plan_days_full)
        if active_mask[i] and ((not d.soup) or (not d.fruit) or (not d.sides) or (len(d.sides) != 3))
    ]

    if ls_enabled and (not incomplete_days) and (not base_errors):
        improved_plan, improved_score, improved_day_details = improve_by_local_search(
            plan_days=plan_days_full,
            mains=mains, sides=sides, soups=soups, fruits=fruits,
            feat=feat,
            hard=hard, weights=weights, soft=soft,
            iterations=int(ls.get("iterations", 800)),
            accept_worse_probability=float(ls.get("accept_worse_probability", 0.03)),
            seed=7,
            start_date=start_date,
            active_mask=active_mask,
        )
        final_plan = improved_plan
        day_details = improved_day_details
        final_score = improved_score
        errors = base_errors
    else:
        final_plan = plan_days_full
        day_details = base_expl
        final_score = base_score
        errors = base_errors

    # explain output（直接用 full，不用再回填）
    result = build_explanations(
        start_date=start_date,
        plan_days=final_plan,
        dishes_by_id=dishes_by_id,
        feat=feat,
        day_scores=day_details
    )
    result["errors"] = errors
    result["ok"] = (len(errors) == 0)

    result.setdefault("debug", {})
    result["debug"]["active_mask"] = active_mask
    result["debug"]["active_days"] = sum(1 for x in active_mask if x)
    result["debug"]["failed_days"] = [e.get("day_index") for e in errors if e.get("day_index") is not None]
    result["debug"]["incomplete_days"] = incomplete_days
    result["debug"]["base_fill_score"] = base_score
    result["debug"]["final_score"] = final_score
    result["debug"]["start_date"] = start_date.isoformat()
    result["debug"]["local_search_enabled"] = (ls_enabled and not incomplete_days and not base_errors)

    return result