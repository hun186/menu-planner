from datetime import date

from src.menu_planner.db.repo import Dish, DishIngredient, Ingredient, InventoryItem, PriceItem
from src.menu_planner.engine.features import build_dish_features


def test_build_dish_features_ignores_zero_qty_inventory_for_bonus():
    dishes = [
        Dish(id="d_main", name="主菜A", role="main", cuisine="tw", meat_type="chicken", tags=[]),
    ]
    dish_ingredients = [
        DishIngredient(dish_id="d_main", ingredient_id="ing_with_stock", qty=1, unit="kg"),
        DishIngredient(dish_id="d_main", ingredient_id="ing_zero_stock", qty=1, unit="kg"),
    ]
    ingredients = {
        "ing_with_stock": Ingredient(
            id="ing_with_stock", name="有庫存", category="veg", protein_group=None, default_unit="kg"
        ),
        "ing_zero_stock": Ingredient(
            id="ing_zero_stock", name="零庫存", category="veg", protein_group=None, default_unit="kg"
        ),
    }
    prices = {
        "ing_with_stock": PriceItem(
            ingredient_id="ing_with_stock", price_date="2026-03-01", price_per_unit=10.0, unit="kg"
        ),
        "ing_zero_stock": PriceItem(
            ingredient_id="ing_zero_stock", price_date="2026-03-22", price_per_unit=5.0, unit="kg"
        ),
    }
    inventory = {
        "ing_with_stock": InventoryItem(
            ingredient_id="ing_with_stock",
            qty_on_hand=3,
            unit="kg",
            updated_at="2026-03-10",
            expiry_date="2026-03-30",
        ),
        # qty_on_hand=0：即便有更新日/到期日，也不應該被視為「有庫存命中」
        "ing_zero_stock": InventoryItem(
            ingredient_id="ing_zero_stock",
            qty_on_hand=0,
            unit="kg",
            updated_at="2026-03-22",
            expiry_date="2026-03-29",
        ),
    }

    feat = build_dish_features(
        dishes=dishes,
        dish_ingredients=dish_ingredients,
        ingredients=ingredients,
        prices=prices,
        inventory=inventory,
        conv={},
        today=date(2026, 3, 20),
    )

    main = feat["d_main"]
    assert main.used_inventory_ingredients == ["ing_with_stock"]
    assert main.inventory_hit_ratio == 0.5
    assert "ing_zero_stock" not in main.inventory_expiry_dates
