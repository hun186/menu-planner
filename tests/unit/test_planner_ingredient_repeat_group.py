from src.menu_planner.db.repo import DishIngredient, Ingredient
from src.menu_planner.engine.planner import _build_dish_ingredient_ids


def _mk_ing(ing_id: str, name: str, protein_group: str | None) -> Ingredient:
    return Ingredient(
        id=ing_id,
        name=name,
        category="soy",
        protein_group=protein_group,
        default_unit="g",
    )


def test_build_dish_ingredient_ids_groups_by_protein_group_when_present():
    ingredients = {
        "ing_tofu_a": _mk_ing("ing_tofu_a", "板豆腐", None),
        "ing_tofu_b": _mk_ing("ing_tofu_b", "嫩豆腐", None),
        "ing_cabbage": _mk_ing("ing_cabbage", "高麗菜", None),
    }
    dish_ingredients = [
        DishIngredient(dish_id="d1", ingredient_id="ing_tofu_a", qty=1, unit="piece"),
        DishIngredient(dish_id="d2", ingredient_id="ing_tofu_b", qty=1, unit="piece"),
        DishIngredient(dish_id="d2", ingredient_id="ing_cabbage", qty=10, unit="g"),
    ]

    got = _build_dish_ingredient_ids(dish_ingredients, ingredients, hard={})

    assert got["d1"] == {"family:tofu"}
    assert got["d2"] == {"family:tofu", "name:高麗菜"}


def test_build_dish_ingredient_ids_does_not_apply_protein_group_to_meat_by_default():
    ingredients = {
        "ing_beef_slice": Ingredient("ing_beef_slice", "牛肉片", "meat", "beef", "g"),
        "ing_beef_cube": Ingredient("ing_beef_cube", "牛肉丁", "meat", "beef", "g"),
    }
    dish_ingredients = [
        DishIngredient(dish_id="d1", ingredient_id="ing_beef_slice", qty=10, unit="g"),
        DishIngredient(dish_id="d2", ingredient_id="ing_beef_cube", qty=10, unit="g"),
    ]

    got = _build_dish_ingredient_ids(dish_ingredients, ingredients, hard={})

    assert got["d1"] == {"ing_beef_slice"}
    assert got["d2"] == {"ing_beef_cube"}


def test_build_dish_ingredient_ids_does_not_group_all_soy_into_tofu_family():
    ingredients = {
        "ing_tofu": Ingredient("ing_tofu", "板豆腐", "soy", None, "piece"),
        "ing_edamame": Ingredient("ing_edamame", "毛豆", "soy", None, "g"),
        "ing_soy_sprout": Ingredient("ing_soy_sprout", "黃豆芽", "soy", None, "g"),
        "ing_fermented_tofu": Ingredient("ing_fermented_tofu", "豆腐乳", "seasoning", None, "piece"),
    }
    dish_ingredients = [
        DishIngredient(dish_id="d1", ingredient_id="ing_tofu", qty=1, unit="piece"),
        DishIngredient(dish_id="d2", ingredient_id="ing_edamame", qty=50, unit="g"),
        DishIngredient(dish_id="d3", ingredient_id="ing_soy_sprout", qty=50, unit="g"),
        DishIngredient(dish_id="d4", ingredient_id="ing_fermented_tofu", qty=1, unit="piece"),
    ]

    got = _build_dish_ingredient_ids(dish_ingredients, ingredients, hard={})

    assert got["d1"] == {"family:tofu"}
    assert got["d2"] == {"name:毛豆"}
    assert got["d3"] == {"name:黃豆芽"}
    assert got["d4"] == {"ing_fermented_tofu"}


def test_build_dish_ingredient_ids_merges_vegetable_shape_variants_by_name():
    ingredients = {
        "ing_carrot_shred": Ingredient("ing_carrot_shred", "紅蘿蔔絲", "vegetable", None, "g"),
        "ing_carrot_dice": Ingredient("ing_carrot_dice", "紅蘿蔔丁", "vegetable", None, "g"),
        "ing_carrot_chunk": Ingredient("ing_carrot_chunk", "紅蘿蔔切塊", "vegetable", None, "g"),
    }
    dish_ingredients = [
        DishIngredient(dish_id="d1", ingredient_id="ing_carrot_shred", qty=10, unit="g"),
        DishIngredient(dish_id="d2", ingredient_id="ing_carrot_dice", qty=10, unit="g"),
        DishIngredient(dish_id="d3", ingredient_id="ing_carrot_chunk", qty=10, unit="g"),
    ]

    got = _build_dish_ingredient_ids(dish_ingredients, ingredients, hard={})

    assert got["d1"] == {"name:紅蘿蔔"}
    assert got["d2"] == {"name:紅蘿蔔"}
    assert got["d3"] == {"name:紅蘿蔔"}
