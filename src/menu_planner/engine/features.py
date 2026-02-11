# src/menu_planner/engine/features.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, List, Tuple, Optional

from ..db.repo import Dish, DishIngredient, InventoryItem, PriceItem, Ingredient

import re

@dataclass(frozen=True)
class DishFeatures:
    dish_id: str
    role: str
    meat_type: Optional[str]
    cuisine: Optional[str]

    cost_per_serving: float
    inventory_hit_ratio: float      # 0~1：用到庫存食材的比例（以品項數粗估）
    near_expiry_days_min: Optional[int]  # 使用到的庫存食材中，最接近到期的天數（越小越急）
    used_inventory_ingredients: List[str]


def _parse_ymd(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def _convert_unit(qty: float, from_unit: str, to_unit: str, conv: Dict[Tuple[str, str], float]) -> Optional[float]:
    if from_unit == to_unit:
        return qty
    factor = conv.get((from_unit, to_unit))
    if factor is None:
        return None
    return qty * factor


def _normalize_meat_type(x: Optional[str]) -> Optional[str]:
    """
    統一 meat_type，避免 fish/seafood/shrimp 等分裂導致 weekly quota 失效。
    回傳值建議維持：pork / beef / chicken / seafood / (None)
    """
    if x is None:
        return None

    s = str(x).strip().lower()
    if not s:
        return None

    # 常見符號/空白統一
    s = re.sub(r"[\s\-_]+", "", s)

    # ✅ 把魚蝦蟹貝等統一成 seafood
    seafood_aliases = {
        "seafood", "fish", "shrimp", "prawn", "crab", "shellfish", "clam", "oyster", "mussel", "squid", "octopus",
        # 你如果資料裡有中文，也可以一起收
        "海鮮", "魚", "蝦", "蟹", "貝", "蛤", "牡蠣", "花枝", "透抽", "章魚",
    }

    # pork/beef/chicken 同義字（看你資料庫怎麼寫，先補常見的）
    pork_aliases = {"pork", "pig", "豬", "豬肉"}
    beef_aliases = {"beef", "cow", "牛", "牛肉"}
    chicken_aliases = {"chicken", "hen", "雞", "雞肉"}

    if s in seafood_aliases:
        return "seafood"
    if s in pork_aliases:
        return "pork"
    if s in beef_aliases:
        return "beef"
    if s in chicken_aliases:
        return "chicken"

    # 其他不認得的值：保守做法是原樣回傳
    # 你也可以改成 return None，讓它不參與 quota（但通常不建議）
    return s
    
def build_dish_features(
    dishes: List[Dish],
    dish_ingredients: List[DishIngredient],
    ingredients: Dict[str, Ingredient],
    prices: Dict[str, PriceItem],
    inventory: Dict[str, InventoryItem],
    conv: Dict[Tuple[str, str], float],
    today: date,
) -> Dict[str, DishFeatures]:
    # group dish ingredients
    di_map: Dict[str, List[DishIngredient]] = {}
    for di in dish_ingredients:
        di_map.setdefault(di.dish_id, []).append(di)

    out: Dict[str, DishFeatures] = {}

    for d in dishes:
        dis = di_map.get(d.id, [])
        total_cost = 0.0

        used_inv: List[str] = []
        inv_hits = 0
        expiry_days_list: List[int] = []

        for di in dis:
            ing = ingredients.get(di.ingredient_id)
            if not ing:
                continue

            # price
            p = prices.get(di.ingredient_id)
            if p:
                # convert di.qty di.unit -> p.unit if needed
                qty_in_price_unit = _convert_unit(di.qty, di.unit, p.unit, conv)
                if qty_in_price_unit is not None:
                    total_cost += qty_in_price_unit * p.price_per_unit

            # inventory hit (by ingredient presence; 可再進一步檢查 qty)
            inv = inventory.get(di.ingredient_id)
            if inv:
                used_inv.append(di.ingredient_id)
                inv_hits += 1

                exp = _parse_ymd(inv.expiry_date)
                if exp:
                    expiry_days_list.append((exp - today).days)

        inv_ratio = (inv_hits / len(dis)) if dis else 0.0
        near_expiry_min = min(expiry_days_list) if expiry_days_list else None

        out[d.id] = DishFeatures(
            dish_id=d.id,
            role=d.role,
            #meat_type=d.meat_type,
            meat_type=_normalize_meat_type(d.meat_type),
            cuisine=d.cuisine,
            cost_per_serving=round(total_cost, 2),
            inventory_hit_ratio=round(inv_ratio, 3),
            near_expiry_days_min=near_expiry_min,
            used_inventory_ingredients=used_inv,
        )

    return out
