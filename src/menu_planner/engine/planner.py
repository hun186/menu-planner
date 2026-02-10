# src/menu_planner/engine/planner.py
from __future__ import annotations

from datetime import date, datetime
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


def plan_month(db_path: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    repo = SQLiteRepo(db_path)

    start_date = _parse_start_date(cfg)
    horizon_days = int(cfg.get("horizon_days", 30))

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

    # beam params
    bt = (search.get("backtracking") or {})
    beam_width = int(bt.get("beam_width", 12))
    cand_limit = int((bt.get("candidate_limit_per_role") or {}).get("main", 25))

    main_ids = plan_mains_beam(
        horizon_days=horizon_days,
        mains=mains,
        feat=feat,
        hard=hard,
        beam_width=beam_width,
        candidate_limit=cand_limit,
        seed=7
    )

    plan_days, base_score, base_expl, base_errors = fill_days_after_mains(
        horizon_days=horizon_days,
        main_ids=main_ids,
        sides=sides,
        soups=soups,
        fruits=fruits,
        feat=feat,
        hard=hard,
        weights=weights,
        soft=soft
    )

    # local search
    ls = (search.get("local_search") or {})
    ls_enabled = bool(ls.get("enabled", True))
    
    # ✅ 偵測「未完成日」：湯/果/配菜不足（或不是 3 道）
    incomplete_days = [
        i for i, d in enumerate(plan_days)
        if (not d.soup) or (not d.fruit) or (not d.sides) or (len(d.sides) != 3)
    ]
    
    if ls_enabled and not incomplete_days and not base_errors:
        improved_plan, improved_score, improved_day_details = improve_by_local_search(
            plan_days=plan_days,
            mains=mains, sides=sides, soups=soups, fruits=fruits,
            feat=feat,
            hard=hard, weights=weights, soft=soft,
            iterations=int(ls.get("iterations", 800)),
            accept_worse_probability=float(ls.get("accept_worse_probability", 0.03)),
            seed=7
        )
        final_plan = improved_plan
        final_score = improved_score
        day_details = improved_day_details
    else:
        # ✅ 有失敗日：直接用 backtracking 的解釋輸出（你 fill_days_after_mains 已經算好）
        final_plan = plan_days
        final_score = base_score
        day_details = base_expl
    

    # explain output
    result = build_explanations(
        start_date=start_date,
        plan_days=final_plan,
        dishes_by_id=dishes_by_id,
        feat=feat,
        day_scores=day_details
    )
    result["errors"] = base_errors
    result["ok"] = (len(base_errors) == 0)
    
    # ✅ 確保 debug 一定存在
    result.setdefault("debug", {})
    result["debug"]["failed_days"] = [e.get("day_index") for e in base_errors if e.get("day_index") is not None]
    result["debug"]["incomplete_days"] = incomplete_days
    result["debug"]["base_fill_score"] = base_score
    result["debug"]["final_score"] = final_score
    result["debug"]["start_date"] = start_date.isoformat()
    result["debug"]["local_search_enabled"] = (ls_enabled and not incomplete_days and not base_errors)

    return result
