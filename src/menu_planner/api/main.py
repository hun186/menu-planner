# src/menu_planner/api/main.py
from __future__ import annotations

import io
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import Body, Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from ..config.loader import load_defaults, validate_config
from ..db.repo import SQLiteRepo
from ..engine.errors import PlanError
from ..engine.planner import plan_month
from .export_excel import build_filename, build_plan_workbook
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


@app.post("/plan")
def post_plan(
    cfg: Dict[str, Any] = Body(...),
    db_path: str = Depends(get_db_path),
):
    result = _run_plan_or_raise(cfg=cfg, db_path=db_path)
    return {"ok": True, "result": result}


@app.post("/export/excel")
def post_export_excel(
    cfg: Dict[str, Any] = Body(...),
    db_path: str = Depends(get_db_path),
):
    result = _run_plan_or_raise(cfg=cfg, db_path=db_path)

    content = build_plan_workbook(cfg=cfg, result=result)
    filename = build_filename("menu_plan")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/admin")
def get_admin_page():
    return FileResponse(UI_DIR / "admin.html")


# 靜態 UI（http://localhost:8000/）
app.mount("/", StaticFiles(directory=str(UI_DIR), html=True), name="ui")
