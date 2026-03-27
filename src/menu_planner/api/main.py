# src/menu_planner/api/main.py
from __future__ import annotations

import io
import re
import traceback
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..config.loader import load_defaults, validate_config
from ..db.repo import SQLiteRepo
from ..engine.constraints import PlanDay
from ..engine.errors import PlanError
from ..engine.features import build_dish_features
from ..engine.local_search import compute_total_score
from ..engine.planner import plan_month
from .export_excel import build_filename, build_plan_workbook
from .procurement import attach_procurement_details
from .routes.admin_catalog import router as admin_catalog_router

APP_DIR = Path(__file__).resolve().parent
PKG_DIR = APP_DIR.parent
UI_DIR = PKG_DIR / "ui_static"

DEFAULT_DB_PATH = str((Path.cwd() / "data" / "menu.db").resolve())

app = FastAPI(title="Menu Planner", version="0.1.0")

app.include_router(admin_catalog_router)


def _error_response(errors: list[Any]) -> Dict[str, Any]:
    return {"ok": False, "errors": errors}


def _raise_api_error(status_code: int, errors: list[Any]) -> None:
    raise HTTPException(status_code=status_code, detail=_error_response(errors))


def _run_plan_or_raise(cfg: Dict[str, Any], db_path: str) -> Dict[str, Any]:
    ok, errs = validate_config(cfg)
    if not ok:
        _raise_api_error(400, errs)

    try:
        return plan_month(db_path=db_path, cfg=cfg)
    except PlanError as e:
        _raise_api_error(400, [e.to_dict()])
    except Exception as e:  # pragma: no cover - defensive API boundary
        _raise_api_error(
            500,
            [{
                "code": "INTERNAL_ERROR",
                "message": str(e),
                "details": {
                    "trace": traceback.format_exc(),
                },
            }],
        )


def _resolve_start_date(cfg: Dict[str, Any], result: Dict[str, Any]) -> date:
    start_date_raw = cfg.get("start_date")
    if isinstance(start_date_raw, str) and start_date_raw.strip():
        return datetime.strptime(start_date_raw.strip(), "%Y-%m-%d").date()
    first_day = (result.get("days") or [{}])[0]
    first_day_date = first_day.get("date")
    if isinstance(first_day_date, str) and first_day_date.strip():
        return datetime.strptime(first_day_date.strip(), "%Y-%m-%d").date()
    return date.today()


def _recompute_scores_for_result(cfg: Dict[str, Any], result: Dict[str, Any], repo: SQLiteRepo) -> None:
    days = result.get("days") or []
    if not days:
        return

    hard = (cfg.get("hard") or {}) if isinstance(cfg, dict) else {}
    soft = (cfg.get("soft") or {}) if isinstance(cfg, dict) else {}
    weights = (cfg.get("weights") or {}) if isinstance(cfg, dict) else {}
    start_date = _resolve_start_date(cfg, result)

    all_dishes = repo.fetch_dishes()
    ingredients = repo.fetch_ingredients()
    dish_ingredients = repo.fetch_dish_ingredients()
    inventory = repo.fetch_inventory()
    prices = repo.fetch_latest_prices()
    unit_conversions = repo.fetch_unit_conversions()
    feat = build_dish_features(
        dishes=all_dishes,
        dish_ingredients=dish_ingredients,
        ingredients=ingredients,
        prices=prices,
        inventory=inventory,
        conv=unit_conversions,
        today=start_date,
    )

    plan_days = []
    for day in days:
        items = day.get("items") or {}
        sides = [s.get("id") for s in (items.get("sides") or []) if isinstance(s, dict) and s.get("id")]
        plan_days.append(
            PlanDay(
                main=(items.get("main") or {}).get("id"),
                sides=sides,
                veg=(items.get("veg") or {}).get("id"),
                soup=(items.get("soup") or {}).get("id"),
                fruit=(items.get("fruit") or {}).get("id"),
            )
        )

    _, details = compute_total_score(
        plan_days=plan_days,
        feat=feat,
        hard=hard,
        weights=weights,
        soft=soft,
        start_date=start_date,
    )
    detail_by_index = {d.get("day_index"): d for d in details if d.get("day_index") is not None}

    total_score = 0.0
    total_fitness = 0.0
    for idx, day in enumerate(days):
        detail = detail_by_index.get(idx)
        if detail is None:
            continue

        raw = round(float(detail.get("score") or 0.0), 2)
        breakdown = detail.get("score_breakdown") or {}
        bonus = round(sum(-float(v) for v in breakdown.values() if float(v) < 0), 2)
        penalty = round(sum(float(v) for v in breakdown.values() if float(v) > 0), 2)
        fitness = round(-raw, 2)

        day["score"] = raw
        day["score_breakdown"] = breakdown
        day["score_fitness"] = fitness
        day["score_summary"] = {
            "bonus": bonus,
            "penalty": penalty,
            "raw": raw,
            "fitness": fitness,
        }
        total_score += raw
        total_fitness += fitness

    summary = result.setdefault("summary", {})
    summary["total_score"] = round(total_score, 2)
    summary["total_fitness"] = round(total_fitness, 2)


def get_db_path(db_path: str = Query(default=DEFAULT_DB_PATH)) -> str:
    return db_path


def get_repo(db_path: str = Depends(get_db_path)) -> SQLiteRepo:
    return SQLiteRepo(db_path)


@app.get("/config/default")
def get_default_config():
    return load_defaults()


@app.post("/config/validate")
def post_validate_config(cfg: Dict[str, Any] = Body(...)):
    ok, errs = validate_config(cfg)
    return {"ok": ok, "errors": errs}


@app.get("/catalog/dishes")
def get_dishes(role: Optional[str] = Query(default=None), repo: SQLiteRepo = Depends(get_repo)):
    dishes = repo.fetch_dishes(role=role)
    return [d.__dict__ for d in dishes]


@app.get("/catalog/ingredients")
def get_ingredients(repo: SQLiteRepo = Depends(get_repo)):
    ings = repo.fetch_ingredients()
    return [v.__dict__ for v in ings.values()]


@app.get("/catalog/summary")
def get_catalog_summary(repo: SQLiteRepo = Depends(get_repo)):
    return repo.fetch_catalog_summary()


@app.post("/plan")
def post_plan(
    cfg: Dict[str, Any] = Body(...),
    db_path: str = Depends(get_db_path),
):
    result = _run_plan_or_raise(cfg=cfg, db_path=db_path)
    enriched = attach_procurement_details(result=result, cfg=cfg, repo=SQLiteRepo(db_path))
    return {"ok": True, "result": enriched}


@app.post("/result/enrich")
def post_enrich_result(
    payload: Dict[str, Any] = Body(...),
    db_path: str = Depends(get_db_path),
):
    cfg = payload.get("cfg") if isinstance(payload.get("cfg"), dict) else {}
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    repo = SQLiteRepo(db_path)
    enriched = attach_procurement_details(result=result, cfg=cfg, repo=repo)
    _recompute_scores_for_result(cfg=cfg, result=enriched, repo=repo)
    return {"ok": True, "result": enriched}


@app.post("/export/excel")
def post_export_excel(
    payload: Dict[str, Any] = Body(...),
    db_path: str = Depends(get_db_path),
):
    cfg = payload.get("cfg") if isinstance(payload.get("cfg"), dict) else payload
    result = payload.get("result") if isinstance(payload.get("result"), dict) else None

    if result is None:
        # backward-compatible: old clients only pass cfg, still allow export
        result = _run_plan_or_raise(cfg=cfg, db_path=db_path)

    enriched = attach_procurement_details(result=result, cfg=cfg, repo=SQLiteRepo(db_path))
    content = build_plan_workbook(cfg=cfg, result=enriched)
    filename = build_filename("menu_plan")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/admin")
def get_admin_page():
    admin_html_path = UI_DIR / "admin.html"
    html = admin_html_path.read_text(encoding="utf-8")
    mtime_token = str(int(admin_html_path.stat().st_mtime))
    html = re.sub(
        r'src="admin\.js(?:\?v=[^"]*)?"',
        f'src="admin.js?v={mtime_token}"',
        html,
    )
    return HTMLResponse(html)


# 靜態 UI（http://localhost:18000/）
app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
