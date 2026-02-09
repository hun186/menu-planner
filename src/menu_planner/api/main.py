# src/menu_planner/api/main.py
from __future__ import annotations

from fastapi import FastAPI, Body, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pathlib import Path
from typing import Any, Dict, Optional

from ..db.repo import SQLiteRepo
from ..config.loader import load_defaults, validate_config
from ..engine.planner import plan_month

import io

from ..api.export_excel import build_plan_workbook, build_filename

APP_DIR = Path(__file__).resolve().parent
PKG_DIR = APP_DIR.parent
UI_DIR = PKG_DIR / "ui_static"

DEFAULT_DB_PATH = str((Path.cwd() / "data" / "menu.db").resolve())

app = FastAPI(title="Menu Planner", version="0.1.0")


@app.get("/config/default")
def get_default_config():
    return load_defaults()


@app.post("/config/validate")
def post_validate_config(cfg: Dict[str, Any] = Body(...)):
    ok, errs = validate_config(cfg)
    return {"ok": ok, "errors": errs}


@app.get("/catalog/dishes")
def get_dishes(role: Optional[str] = Query(default=None), db_path: str = Query(default=DEFAULT_DB_PATH)):
    repo = SQLiteRepo(db_path)
    dishes = repo.fetch_dishes(role=role)
    return [d.__dict__ for d in dishes]


@app.get("/catalog/ingredients")
def get_ingredients(db_path: str = Query(default=DEFAULT_DB_PATH)):
    repo = SQLiteRepo(db_path)
    ings = repo.fetch_ingredients()
    return [v.__dict__ for v in ings.values()]


@app.post("/plan")
def post_plan(
    cfg: Dict[str, Any] = Body(...),
    db_path: str = Query(default=DEFAULT_DB_PATH)
):
    ok, errs = validate_config(cfg)
    if not ok:
        return {"ok": False, "errors": errs}

    result = plan_month(db_path=db_path, cfg=cfg)
    return {"ok": True, "result": result}

@app.post("/export/excel")
def post_export_excel(
    cfg: Dict[str, Any] = Body(...),
    db_path: str = Query(default=DEFAULT_DB_PATH)
):
    ok, errs = validate_config(cfg)
    if not ok:
        raise HTTPException(status_code=400, detail=errs)

    result = plan_month(db_path=db_path, cfg=cfg)
    content = build_plan_workbook(cfg=cfg, result=result)

    filename = build_filename("menu_plan")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


# 靜態 UI（http://localhost:8000/）
app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
