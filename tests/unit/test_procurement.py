from src.menu_planner.api.procurement import build_procurement_days
from src.menu_planner.db.repo import DishIngredient, Ingredient, PriceItem


def test_build_procurement_days_applies_people_and_price_conversion():
    result = {
        "days": [
            {
                "date": "2026-03-20",
                "day_index": 0,
                "items": {
                    "main": {"id": "m1", "name": "紅燒豆腐"},
                    "sides": [],
                    "veg": {},
                    "soup": {},
                    "fruit": {},
                },
            }
        ]
    }

    dish_ingredients = [DishIngredient(dish_id="m1", ingredient_id="ing1", qty=100, unit="g")]
    ingredients = {"ing1": Ingredient(id="ing1", name="豆腐", category="protein", protein_group=None, default_unit="g")}
    prices = {"ing1": PriceItem(ingredient_id="ing1", price_date="2026-03-01", price_per_unit=0.2, unit="kg")}
    conv = {("g", "kg"): 0.001}

    days = build_procurement_days(
        result=result,
        people=50,
        dish_ingredients=dish_ingredients,
        ingredients=ingredients,
        prices=prices,
        unit_conversions=conv,
    )

    ing = days[0]["dishes"][0]["ingredients"][0]
    assert ing["qty_for_people"] == 5000
    assert ing["unit_price"] == 0.2
    assert ing["line_total"] == 1.0
    assert days[0]["day_total"] == 1.0
