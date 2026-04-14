from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..db.repo import DishIngredient, Ingredient, PriceItem, SQLiteRepo


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _convert_unit(qty: float, from_unit: str, to_unit: str, conv: Dict[Tuple[str, str], float]) -> Optional[float]:
    if from_unit == to_unit:
        return qty
    factor = conv.get((from_unit, to_unit))
    if factor is not None:
        return qty * factor
    inverse = conv.get((to_unit, from_unit))
    if inverse is not None and float(inverse) != 0:
        return qty / float(inverse)
    return None


def _iter_day_dishes(day: Dict[str, Any]) -> Iterable[Tuple[str, Dict[str, Any]]]:
    items = day.get("items") or {}
    for role in ("main", "veg", "soup", "fruit"):
        dish = items.get(role) or {}
        if dish.get("id"):
            yield role, dish

    for side in (items.get("sides") or []):
        if (side or {}).get("id"):
            yield "side", side


def _resolve_day_people(
    day: Dict[str, Any],
    default_people: int,
    people_overrides: Dict[str, Any],
) -> int:
    date_key = str(day.get("date") or "").strip()
    day_index = day.get("day_index")
    override = None
    if date_key and date_key in people_overrides:
        override = people_overrides.get(date_key)
    elif day_index is not None and str(day_index) in people_overrides:
        override = people_overrides.get(str(day_index))
    try:
        return max(1, int(_to_float(override, default_people)))
    except Exception:
        return default_people


def build_procurement_days(
    result: Dict[str, Any],
    default_people: int,
    people_overrides: Optional[Dict[str, Any]],
    dish_ingredients: List[DishIngredient],
    ingredients: Dict[str, Ingredient],
    prices: Dict[str, PriceItem],
    unit_conversions: Dict[Tuple[str, str], float],
) -> List[Dict[str, Any]]:
    by_dish: Dict[str, List[DishIngredient]] = defaultdict(list)
    for di in dish_ingredients:
        by_dish[di.dish_id].append(di)

    out_days: List[Dict[str, Any]] = []
    override_map = people_overrides or {}
    for day in (result.get("days") or []):
        people = _resolve_day_people(day, default_people=default_people, people_overrides=override_map)
        dish_rows: List[Dict[str, Any]] = []
        day_total = 0.0

        for role, dish in _iter_day_dishes(day):
            dish_id = dish.get("id")
            if not dish_id:
                continue

            ingredient_rows: List[Dict[str, Any]] = []
            dish_total = 0.0
            for di in by_dish.get(dish_id, []):
                ing = ingredients.get(di.ingredient_id)
                ingredient_name = ing.name if ing else di.ingredient_id

                qty_for_people = round(di.qty * people, 4)
                price = prices.get(di.ingredient_id)

                unit_price = None
                unit_price_unit = None
                line_total = None
                price_date = None

                if price:
                    qty_in_price_unit = _convert_unit(qty_for_people, di.unit, price.unit, unit_conversions)
                    if qty_in_price_unit is not None:
                        unit_price = round(float(price.price_per_unit), 4)
                        unit_price_unit = price.unit
                        line_total = round(float(qty_in_price_unit) * float(price.price_per_unit), 2)
                        price_date = price.price_date
                        dish_total += line_total

                ingredient_rows.append({
                    "ingredient_id": di.ingredient_id,
                    "ingredient_name": ingredient_name,
                    "qty_per_person": round(di.qty, 4),
                    "qty_for_people": qty_for_people,
                    "qty_unit": di.unit,
                    "unit_price": unit_price,
                    "unit_price_unit": unit_price_unit,
                    "line_total": line_total,
                    "price_date": price_date,
                })

            dish_rows.append({
                "role": role,
                "dish_id": dish_id,
                "dish_name": dish.get("name") or dish_id,
                "ingredients": ingredient_rows,
                "dish_total": round(dish_total, 2),
            })
            day_total += dish_total

        out_days.append({
            "date": day.get("date"),
            "day_index": day.get("day_index"),
            "people": people,
            "dishes": dish_rows,
            "day_total": round(day_total, 2),
        })

    return out_days


def attach_procurement_details(result: Dict[str, Any], cfg: Dict[str, Any], repo: SQLiteRepo) -> Dict[str, Any]:
    people = max(1, int(_to_float((cfg or {}).get("people"), 250)))
    schedule = (cfg or {}).get("schedule") or {}
    people_overrides = schedule.get("people_overrides") if isinstance(schedule, dict) else {}

    dish_ids: List[str] = []
    for day in (result.get("days") or []):
        for _, dish in _iter_day_dishes(day):
            if dish.get("id"):
                dish_ids.append(dish["id"])
    dish_ids = sorted(set(dish_ids))

    dish_ingredients = repo.fetch_dish_ingredients(dish_ids)
    ingredients = repo.fetch_ingredients()
    prices = repo.fetch_latest_prices()
    unit_conversions = repo.fetch_unit_conversions()

    procurement_days = build_procurement_days(
        result=result,
        default_people=people,
        people_overrides=people_overrides,
        dish_ingredients=dish_ingredients,
        ingredients=ingredients,
        prices=prices,
        unit_conversions=unit_conversions,
    )

    for day, detail in zip((result.get("days") or []), procurement_days):
        day["procurement"] = detail

    summary = result.setdefault("summary", {})
    summary["people"] = people
    summary["people_overrides"] = people_overrides or {}
    return result
