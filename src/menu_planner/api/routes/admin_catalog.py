#src/menu_planner/api/routes/admin_catalog.py
from __future__ import annotations

import os
import sqlite3
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from ...db.admin_repo import SQLiteAdminRepo

DEFAULT_DB_PATH = str((__import__("pathlib").Path.cwd() / "data" / "menu.db").resolve())

router = APIRouter(prefix="/admin/catalog", tags=["admin-catalog"])

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
    role: str = Field(pattern="^(main|side|soup|fruit)$")
    cuisine: Optional[str] = None
    meat_type: Optional[str] = None
    tags: List[str] = Field(default_factory=list)

class DishIngredientIn(BaseModel):
    ingredient_id: str = Field(min_length=1)
    qty: float = Field(gt=0)
    unit: str = Field(min_length=1)

@router.put("/ingredients/{ingredient_id}", dependencies=[Depends(require_admin_key)])
def upsert_ingredient(
    ingredient_id: str,
    body: IngredientUpsert,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    repo.upsert_ingredient(ingredient_id, body.model_dump())
    return {"ok": True, "id": ingredient_id}

@router.delete("/ingredients/{ingredient_id}", dependencies=[Depends(require_admin_key)])
def delete_ingredient(
    ingredient_id: str,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
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
    updated_at: str = Field(min_length=10)           # YYYY-MM-DD
    expiry_date: Optional[str] = None                # YYYY-MM-DD or null

@router.get("/ingredients/{ingredient_id}/prices", dependencies=[Depends(require_admin_key)])
def list_prices(
    ingredient_id: str,
    limit: int = Query(default=30, ge=1, le=365),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    if not repo.ingredient_exists(ingredient_id):
        raise HTTPException(status_code=404, detail="找不到此食材")
    return repo.list_prices(ingredient_id, limit=limit)

@router.put("/ingredients/{ingredient_id}/prices/{price_date}", dependencies=[Depends(require_admin_key)])
def upsert_price(
    ingredient_id: str,
    price_date: str,
    body: PriceUpsert,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    if not repo.ingredient_exists(ingredient_id):
        raise HTTPException(status_code=404, detail="找不到此食材")
    repo.upsert_price(ingredient_id, price_date, body.model_dump())
    return {"ok": True}

@router.delete("/ingredients/{ingredient_id}/prices/{price_date}", dependencies=[Depends(require_admin_key)])
def delete_price(
    ingredient_id: str,
    price_date: str,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    n = repo.delete_price(ingredient_id, price_date)
    if n == 0:
        raise HTTPException(status_code=404, detail="找不到此價格紀錄")
    return {"ok": True}

@router.get("/ingredients/{ingredient_id}/inventory", dependencies=[Depends(require_admin_key)])
def get_inventory(
    ingredient_id: str,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    if not repo.ingredient_exists(ingredient_id):
        raise HTTPException(status_code=404, detail="找不到此食材")
    return repo.get_inventory(ingredient_id)  # 可能回 null

@router.put("/ingredients/{ingredient_id}/inventory", dependencies=[Depends(require_admin_key)])
def upsert_inventory(
    ingredient_id: str,
    body: InventoryUpsert,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    if not repo.ingredient_exists(ingredient_id):
        raise HTTPException(status_code=404, detail="找不到此食材")
    repo.upsert_inventory(ingredient_id, body.model_dump())
    return {"ok": True}

@router.put("/dishes/{dish_id}", dependencies=[Depends(require_admin_key)])
def upsert_dish(
    dish_id: str,
    body: DishUpsert,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    repo.upsert_dish(dish_id, body.model_dump())
    return {"ok": True, "id": dish_id}

@router.delete("/dishes/{dish_id}", dependencies=[Depends(require_admin_key)])
def delete_dish(
    dish_id: str,
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
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
    if not repo.dish_exists(dish_id):
        raise HTTPException(status_code=404, detail="找不到此菜色")
    return repo.get_dish_ingredients(dish_id)

@router.put("/dishes/{dish_id}/ingredients", dependencies=[Depends(require_admin_key)])
def put_dish_ingredients(
    dish_id: str,
    items: List[DishIngredientIn] = Body(...),
    db_path: str = Query(default=DEFAULT_DB_PATH),
):
    repo = SQLiteAdminRepo(db_path)
    if not repo.dish_exists(dish_id):
        raise HTTPException(status_code=404, detail="找不到此菜色")

    missing = repo.find_missing_ingredients([x.ingredient_id for x in items])
    if missing:
        raise HTTPException(status_code=400, detail={"message": "有不存在的食材 id", "missing": missing})

    repo.replace_dish_ingredients(dish_id, [x.model_dump() for x in items])
    return {"ok": True}
