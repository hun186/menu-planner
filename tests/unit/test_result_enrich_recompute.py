from src.menu_planner.api.main import _recompute_scores_for_result
from src.menu_planner.db.repo import Dish, DishIngredient, Ingredient, InventoryItem, PriceItem


class _FakeRepo:
    def fetch_dishes(self):
        return [
            Dish(id="main_chicken", name="雞肉主菜", role="main", cuisine="tw", meat_type="chicken", tags=[]),
            Dish(id="main_pork", name="豬肉主菜", role="main", cuisine="tw", meat_type="pork", tags=[]),
            Dish(id="side_a", name="配菜A", role="side", cuisine="tw", meat_type=None, tags=[]),
            Dish(id="side_b", name="配菜B", role="side", cuisine="tw", meat_type=None, tags=[]),
            Dish(id="veg_a", name="青菜", role="veg", cuisine="tw", meat_type=None, tags=[]),
            Dish(id="soup_a", name="湯", role="soup", cuisine="tw", meat_type=None, tags=[]),
            Dish(id="fruit_a", name="水果", role="fruit", cuisine="tw", meat_type=None, tags=[]),
        ]

    def fetch_ingredients(self):
        return {
            "ing_main": Ingredient(id="ing_main", name="主料", category="protein", protein_group=None, default_unit="g"),
            "ing_side": Ingredient(id="ing_side", name="配料", category="veg", protein_group=None, default_unit="g"),
        }

    def fetch_dish_ingredients(self):
        return [
            DishIngredient(dish_id="main_chicken", ingredient_id="ing_main", qty=100, unit="g"),
            DishIngredient(dish_id="main_pork", ingredient_id="ing_main", qty=100, unit="g"),
            DishIngredient(dish_id="side_a", ingredient_id="ing_side", qty=30, unit="g"),
            DishIngredient(dish_id="side_b", ingredient_id="ing_side", qty=30, unit="g"),
            DishIngredient(dish_id="veg_a", ingredient_id="ing_side", qty=30, unit="g"),
            DishIngredient(dish_id="soup_a", ingredient_id="ing_side", qty=30, unit="g"),
            DishIngredient(dish_id="fruit_a", ingredient_id="ing_side", qty=30, unit="g"),
        ]

    def fetch_inventory(self):
        return {
            "ing_main": InventoryItem(
                ingredient_id="ing_main",
                qty_on_hand=1000,
                unit="g",
                updated_at="2026-03-20",
                expiry_date="2026-03-30",
            ),
        }

    def fetch_latest_prices(self):
        return {
            "ing_main": PriceItem(ingredient_id="ing_main", price_date="2026-03-01", price_per_unit=0.02, unit="g"),
            "ing_side": PriceItem(ingredient_id="ing_side", price_date="2026-03-01", price_per_unit=0.01, unit="g"),
        }

    def fetch_unit_conversions(self):
        return {}


def _day(main_id: str):
    return {
        "items": {
            "main": {"id": main_id},
            "sides": [{"id": "side_a"}, {"id": "side_b"}],
            "veg": {"id": "veg_a"},
            "soup": {"id": "soup_a"},
            "fruit": {"id": "fruit_a"},
        }
    }


def test_recompute_scores_updates_consecutive_penalty_and_summary():
    cfg = {
        "start_date": "2026-03-20",
        "hard": {"cost_range_per_person_per_day": {"min": 0, "max": 999}},
        "weights": {"consecutive_same_meat_penalty": 5},
        "soft": {},
    }
    result = {"days": [_day("main_chicken"), _day("main_pork")], "summary": {}}

    repo = _FakeRepo()
    _recompute_scores_for_result(cfg=cfg, result=result, repo=repo)
    no_repeat_day2 = result["days"][1]["score"]

    result["days"][1]["items"]["main"]["id"] = "main_chicken"
    _recompute_scores_for_result(cfg=cfg, result=result, repo=repo)
    repeated_day2 = result["days"][1]["score"]

    assert repeated_day2 > no_repeat_day2
    assert result["days"][1]["score_breakdown"].get("consecutive_same_meat") == 5
    assert result["summary"]["total_score"] == round(
        result["days"][0]["score"] + result["days"][1]["score"], 2
    )
