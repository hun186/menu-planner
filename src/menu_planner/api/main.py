# src/menu_planner/api/main.py
from __future__ import annotations

from fastapi import FastAPI, Body, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from fastapi.responses import FileResponse
from pathlib import Path
from typing import Any, Dict, Optional
import io
import traceback

from ..db.repo import SQLiteRepo
from ..config.loader import load_defaults, validate_config
from ..engine.planner import plan_month
from ..engine.errors import PlanError  # ✅ 確保有匯入

from .routes.admin_catalog import router as admin_catalog_router

from ..api.export_excel import build_plan_workbook, build_filename

APP_DIR = Path(__file__).resolve().parent
PKG_DIR = APP_DIR.parent
UI_DIR = PKG_DIR / "ui_static"

DEFAULT_DB_PATH = str((Path.cwd() / "data" / "menu.db").resolve())

app = FastAPI(title="Menu Planner", version="0.1.0")

app.include_router(admin_catalog_router)

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
    print("DEBUG: post_plan reached")  # 觀察 console 是否有印
    ok, errs = validate_config(cfg)
    if not ok:
        return {"ok": False, "errors": errs}

    try:
        result = plan_month(db_path=db_path, cfg=cfg)
        return {"ok": True, "result": result}
    except PlanError as e:
        # 你自己的可預期錯誤
        return {"ok": False, "errors": [e.to_dict()]}
    except Exception as e:
        # ✅ 未預期錯誤：回傳 traceback 讓 UI/你自己能定位
        return {
            "ok": False,
            "errors": [{
                "code": "INTERNAL_ERROR",
                "message": str(e),
                "details": {
                    "trace": traceback.format_exc()
                }
            }]
        }
    
@app.post("/export/excel")
def post_export_excel(
    cfg: Dict[str, Any] = Body(...),
    db_path: str = Query(default=DEFAULT_DB_PATH)
):
    ok, errs = validate_config(cfg)
    if not ok:
        raise HTTPException(status_code=400, detail=errs)

    try:
        result = plan_month(db_path=db_path, cfg=cfg)
    except PlanError as e:
        raise HTTPException(status_code=400, detail=e.to_dict())

    content = build_plan_workbook(cfg=cfg, result=result)
    filename = build_filename("menu_plan")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/admin")
def get_admin_page():
    return FileResponse(UI_DIR / "admin.html")

# 靜態 UI（http://localhost:8000/）
app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
