from src.menu_planner.db.repo import Dish, DishIngredient
from src.menu_planner.engine.planner import _filter_dishes_by_excluded_ingredients


def _mk_dish(dish_id: str, role: str = "main") -> Dish:
    return Dish(
        id=dish_id,
        name=dish_id,
        role=role,
        cuisine="taiwanese",
        meat_type=None,
        tags=[],
    )


def _mk_di(dish_id: str, ingredient_id: str) -> DishIngredient:
    return DishIngredient(
        dish_id=dish_id,
        ingredient_id=ingredient_id,
        qty=1.0,
        unit="份",
    )


def test_filter_dishes_by_excluded_ingredients_removes_matching_dishes():
    dishes = [_mk_dish("d1"), _mk_dish("d2"), _mk_dish("d3")]
    dish_ingredients = [
        _mk_di("d1", "ing_tofu"),
        _mk_di("d2", "ing_cabbage"),
    ]
    hard = {"exclude_ingredient_ids": ["ing_tofu"]}

    filtered = _filter_dishes_by_excluded_ingredients(dishes, dish_ingredients, hard)

    assert [d.id for d in filtered] == ["d2", "d3"]


def test_filter_dishes_by_excluded_ingredients_keeps_all_when_empty():
    dishes = [_mk_dish("d1"), _mk_dish("d2")]
    dish_ingredients = [
        _mk_di("d1", "ing_tofu"),
        _mk_di("d2", "ing_cabbage"),
    ]
    hard = {"exclude_ingredient_ids": []}

    filtered = _filter_dishes_by_excluded_ingredients(dishes, dish_ingredients, hard)

    assert [d.id for d in filtered] == ["d1", "d2"]
