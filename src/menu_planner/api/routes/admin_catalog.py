#src/menu_planner/api/routes/admin_catalog.py
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field

from ...db.admin_repo import SQLiteAdminRepo
from ...db.backup import create_db_backup

DEFAULT_DB_PATH = str((__import__("pathlib").Path.cwd() / "data" / "menu.db").resolve())

router = APIRouter(prefix="/admin/catalog", tags=["admin-catalog"])


def _timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _build_excel_response(filename_prefix: str, sheet_name: str, headers: List[str], rows: List[List[object]]) -> StreamingResponse:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31] if sheet_name else "sheet1"
    ws.append(headers)
    for row in rows:
        ws.append(row)

    for idx, title in enumerate(headers, start=1):
        col = ws.column_dimensions[get_column_letter(idx)]
        col.width = max(12, min(40, len(str(title)) + 6))
        ws.cell(row=1, column=idx).font = Font(bold=True)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"{filename_prefix}_{_timestamp_for_filename()}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def backup_before_modify(db_path: str) -> None:
    try:
        create_db_backup(db_path)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail=f"資料庫檔案不存在：{db_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"建立資料庫備份失敗：{e}")


def repo_with_backup(db_path: str) -> SQLiteAdminRepo:
    backup_before_modify(db_path)
    return SQLiteAdminRepo(db_path)


def ensure_ingredient_exists(repo: SQLiteAdminRepo, ingredient_id: str) -> None:
    if not repo.ingredient_exists(ingredient_id):
        raise HTTPException(status_code=404, detail="找不到此食材")


def ensure_dish_exists(repo: SQLiteAdminRepo, dish_id: str) -> None:
    if not repo.dish_exists(dish_id):
        raise HTTPException(status_code=404, detail="找不到此菜色")


def require_admin_key(x_admin_key: Optional[str] = Header(default=None)):
    required = os.getenv("MENU_ADMIN_KEY")
    if required and x_admin_key != required:
        raise HTTPException(status_code=401, detail="未授權：需要有效的 X-Admin-Key")


class IngredientUpsert(BaseModel):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    protein_group: Optional[str] = None
    default_unit: str = Field(min_length=1)


class DishUpsert(BaseModel):
    name: str = Field(min_length=1)
    role: str = Field(pattern="^(main|side|veg|soup|fruit)$")
    cuisine: Optional[str] = None
    meat_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class DishIngredientIn(BaseModel):
    ingredient_id: str = Field(min_length=1)
    qty: float = Field(gt=0)
    unit: str = Field(min_length=1)


class DishCostPreviewIn(BaseModel):
    items: List[DishIngredientIn] = Field(default_factory=list)
    servings: float = Field(default=1.0, gt=0)


@router.get("/ingredients", dependencies=[Depends(require_admin_key)])
def list_ingredients(
    q: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    return repo.list_ingredients(q=q, page=page, page_size=page_size)


@router.get("/dishes", dependencies=[Depends(require_admin_key)])
def list_dishes(
    q: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    ingredient_id: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    return repo.list_dishes(q=q, role=role, ingredient_id=ingredient_id, page=page, page_size=page_size)


@router.put("/ingredients/{ingredient_id}", dependencies=[Depends(require_admin_key)])
def upsert_ingredient(
    ingredient_id: str,
    body: IngredientUpsert,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = repo_with_backup(db_path)
    repo.upsert_ingredient(ingredient_id, body.model_dump())
    return {"ok": True, "id": ingredient_id}


@router.delete("/ingredients/{ingredient_id}", dependencies=[Depends(require_admin_key)])
def delete_ingredient(
    ingredient_id: str,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    ensure_ingredient_exists(repo, ingredient_id)

    repo = repo_with_backup(db_path)
    try:
        n = repo.delete_ingredient(ingredient_id)
        if n == 0:
            raise HTTPException(status_code=404, detail="找不到此食材")
        return {"ok": True}
    except sqlite3.IntegrityError:
        refs = repo.find_dishes_using_ingredient(ingredient_id)
        raise HTTPException(
            status_code=409,
            detail={"message": "此食材已被菜色引用，無法刪除", "referenced_by": refs},
        )


class PriceUpsert(BaseModel):
    price_per_unit: float = Field(gt=0)
    unit: str = Field(min_length=1)


class InventoryUpsert(BaseModel):
    qty_on_hand: float = Field(ge=0)
    unit: str = Field(min_length=1)
    updated_at: str = Field(min_length=10)  # YYYY-MM-DD
    expiry_date: Optional[str] = None  # YYYY-MM-DD or null


class IngredientMergeIn(BaseModel):
    source_ingredient_id: str = Field(min_length=1)
    target_ingredient_id: str = Field(min_length=1)


@router.get("/ingredients/{ingredient_id}/prices", dependencies=[Depends(require_admin_key)])
def list_prices(
    ingredient_id: str,
    limit: int = Query(default=30, ge=1, le=365),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    ensure_ingredient_exists(repo, ingredient_id)
    return repo.list_prices(ingredient_id, limit=limit)


@router.put("/ingredients/{ingredient_id}/prices/{price_date}", dependencies=[Depends(require_admin_key)])
def upsert_price(
    ingredient_id: str,
    price_date: str,
    body: PriceUpsert,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    ensure_ingredient_exists(repo, ingredient_id)

    repo = repo_with_backup(db_path)
    repo.upsert_price(ingredient_id, price_date, body.model_dump())
    return {"ok": True}


@router.delete("/ingredients/{ingredient_id}/prices/{price_date}", dependencies=[Depends(require_admin_key)])
def delete_price(
    ingredient_id: str,
    price_date: str,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    ensure_ingredient_exists(repo, ingredient_id)
    if not repo.price_exists(ingredient_id, price_date):
        raise HTTPException(status_code=404, detail="找不到此價格紀錄")

    repo = repo_with_backup(db_path)
    repo.delete_price(ingredient_id, price_date)
    return {"ok": True}


@router.get("/ingredients/{ingredient_id}/inventory", dependencies=[Depends(require_admin_key)])
def get_inventory(
    ingredient_id: str,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    ensure_ingredient_exists(repo, ingredient_id)
    return repo.get_inventory(ingredient_id)  # 可能回 null


@router.put("/ingredients/{ingredient_id}/inventory", dependencies=[Depends(require_admin_key)])
def upsert_inventory(
    ingredient_id: str,
    body: InventoryUpsert,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    ensure_ingredient_exists(repo, ingredient_id)

    repo = repo_with_backup(db_path)
    repo.upsert_inventory(ingredient_id, body.model_dump())
    return {"ok": True}


@router.get("/inventory/summary", dependencies=[Depends(require_admin_key)])
def list_inventory_summary(
    q: Optional[str] = Query(default=None),
    only_in_stock: bool = Query(default=False),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    return repo.list_inventory_summary(q=q, only_in_stock=only_in_stock)


@router.post("/inventory/summary/merge-ingredient", dependencies=[Depends(require_admin_key)])
def merge_inventory_ingredient(
    body: IngredientMergeIn,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    source_id = body.source_ingredient_id.strip()
    target_id = body.target_ingredient_id.strip()
    repo = SQLiteAdminRepo(db_path)
    ensure_ingredient_exists(repo, source_id)
    ensure_ingredient_exists(repo, target_id)

    repo = repo_with_backup(db_path)
    try:
        result = repo.merge_ingredient(source_id, target_id)
        return {"ok": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/inventory/summary/export", dependencies=[Depends(require_admin_key)])
def export_inventory_summary_excel(
    q: Optional[str] = Query(default=None),
    only_in_stock: bool = Query(default=False),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    rows_raw = repo.list_inventory_summary(q=q, only_in_stock=only_in_stock)
    rows = [
        [
            r.get("ingredient_id"),
            r.get("ingredient_name"),
            r.get("category"),
            r.get("qty_on_hand"),
            r.get("inventory_unit") or r.get("default_unit"),
            r.get("updated_at"),
            r.get("expiry_date"),
            r.get("dish_ref_count"),
        ]
        for r in rows_raw
    ]
    return _build_excel_response(
        filename_prefix="inventory_summary",
        sheet_name="庫存統整",
        headers=["食材ID", "名稱", "分類", "庫存量", "庫存單位", "更新日", "到期日", "引用菜色數"],
        rows=rows,
    )


@router.get("/ingredients/export", dependencies=[Depends(require_admin_key)])
def export_ingredients_excel(
    q: Optional[str] = Query(default=None),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    payload = repo.list_ingredients(q=q, page=1, page_size=100000)
    items = payload.get("items") or []
    rows = [
        [r.get("id"), r.get("name"), r.get("category"), r.get("protein_group"), r.get("default_unit")]
        for r in items
    ]
    return _build_excel_response(
        filename_prefix="ingredients",
        sheet_name="食材管理",
        headers=["食材ID", "名稱", "分類", "蛋白群組", "預設單位"],
        rows=rows,
    )


@router.get("/dishes/export", dependencies=[Depends(require_admin_key)])
def export_dishes_excel(
    q: Optional[str] = Query(default=None),
    ingredient_id: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    payload = repo.list_dishes(q=q, role=role, ingredient_id=ingredient_id, page=1, page_size=100000)
    items = payload.get("items") or []
    rows = [
        [
            r.get("id"),
            r.get("name"),
            r.get("role"),
            r.get("meat_type"),
            r.get("cuisine"),
            ",".join(r.get("tags") or []),
        ]
        for r in items
    ]
    return _build_excel_response(
        filename_prefix="dishes",
        sheet_name="菜名管理",
        headers=["菜色ID", "名稱", "角色", "肉類", "菜系", "標籤"],
        rows=rows,
    )


@router.put("/dishes/{dish_id}", dependencies=[Depends(require_admin_key)])
def upsert_dish(
    dish_id: str,
    body: DishUpsert,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = repo_with_backup(db_path)
    repo.upsert_dish(dish_id, body.model_dump())
    return {"ok": True, "id": dish_id}


@router.delete("/dishes/{dish_id}", dependencies=[Depends(require_admin_key)])
def delete_dish(
    dish_id: str,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    ensure_dish_exists(repo, dish_id)

    repo = repo_with_backup(db_path)
    n = repo.delete_dish(dish_id)
    if n == 0:
        raise HTTPException(status_code=404, detail="找不到此菜色")
    return {"ok": True}


@router.get("/dishes/{dish_id}/ingredients", dependencies=[Depends(require_admin_key)])
def get_dish_ingredients(
    dish_id: str,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    ensure_dish_exists(repo, dish_id)
    return repo.get_dish_ingredients(dish_id)


@router.put("/dishes/{dish_id}/ingredients", dependencies=[Depends(require_admin_key)])
def put_dish_ingredients(
    dish_id: str,
    items: List[DishIngredientIn] = Body(...),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    ensure_dish_exists(repo, dish_id)

    missing = repo.find_missing_ingredients([x.ingredient_id for x in items])
    if missing:
        raise HTTPException(status_code=400, detail={"message": "有不存在的食材 id", "missing": missing})

    repo = repo_with_backup(db_path)
    repo.replace_dish_ingredients(dish_id, [x.model_dump() for x in items])
    return {"ok": True}


@router.post("/dishes/cost-preview", dependencies=[Depends(require_admin_key)])
def dish_cost_preview(
    body: DishCostPreviewIn,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    return repo.preview_dish_cost([x.model_dump() for x in body.items], servings=body.servings)


@router.get("/dishes/cost-preview", dependencies=[Depends(require_admin_key)])
def list_dish_cost_preview(
    dish_id: List[str] = Query(default=[]),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    dish_ids = dish_id if isinstance(dish_id, list) else []
    target_dish_ids = dish_ids or None
    if target_dish_ids is None:
        return repo.list_dish_cost_preview()
    return repo.list_dish_cost_preview(target_dish_ids)
