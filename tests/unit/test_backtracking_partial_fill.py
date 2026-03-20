from datetime import date

from src.menu_planner.db.repo import Dish
from src.menu_planner.engine.backtracking import fill_days_after_mains
from src.menu_planner.engine.features import DishFeatures


def _mk_dish(dish_id: str, role: str) -> Dish:
    return Dish(
        id=dish_id,
        name=dish_id,
        role=role,
        cuisine="tw",
        meat_type="pork" if role == "main" else None,
        tags=[],
    )


def _mk_feat(dish_id: str, role: str, meat_type: str | None = None) -> DishFeatures:
    return DishFeatures(
        dish_id=dish_id,
        role=role,
        meat_type=meat_type,
        cuisine="tw",
        cost_per_serving=10.0,
        inventory_hit_ratio=0.0,
        near_expiry_days_min=None,
        used_inventory_ingredients=[],
    )


def test_fill_days_after_mains_keeps_sides_and_fruit_when_soup_fails():
    mains = ["main_day0", "main_day1"]
    sides = [_mk_dish("side_day0_a", "side"), _mk_dish("side_day0_b", "side"), _mk_dish("side_day1_a", "side"), _mk_dish("side_day1_b", "side")]
    vegs = [_mk_dish("veg_day0", "veg"), _mk_dish("veg_day1", "veg")]
    soups = [_mk_dish("soup_day0", "soup"), _mk_dish("soup_day1_blocked", "soup")]
    fruits = [_mk_dish("fruit_day0", "fruit"), _mk_dish("fruit_day1", "fruit")]

    feat = {
        "main_day0": _mk_feat("main_day0", "main", meat_type="pork"),
        "main_day1": _mk_feat("main_day1", "main", meat_type="chicken"),
        "side_day0_a": _mk_feat("side_day0_a", "side"),
        "side_day0_b": _mk_feat("side_day0_b", "side"),
        "side_day1_a": _mk_feat("side_day1_a", "side"),
        "side_day1_b": _mk_feat("side_day1_b", "side"),
        "veg_day0": _mk_feat("veg_day0", "veg"),
        "veg_day1": _mk_feat("veg_day1", "veg"),
        "soup_day0": _mk_feat("soup_day0", "soup"),
        "soup_day1_blocked": _mk_feat("soup_day1_blocked", "soup"),
        "fruit_day0": _mk_feat("fruit_day0", "fruit"),
        "fruit_day1": _mk_feat("fruit_day1", "fruit"),
    }

    hard = {
        "seed": 7,
        "repeat_limits": {
            "max_same_soup_in_7_days": 2,
            "max_same_side_in_7_days": 2,
            "max_same_veg_in_7_days": 2,
            "max_same_fruit_in_7_days": 2,
            "max_same_ingredient_in_window_days": 1,
            "ingredient_repeat_window_days": 4,
        },
        "cost_range_per_person_per_day": {"min": 0, "max": 999},
    }
    weights = {}
    soft = {}
    dish_ingredient_ids = {
        "main_day0": {"ing_main0"},
        "main_day1": {"ing_main1"},
        "side_day0_a": {"ing_side0a"},
        "side_day0_b": {"ing_side0b"},
        "side_day1_a": {"ing_side1a"},
        "side_day1_b": {"ing_side1b"},
        "veg_day0": {"ing_veg0"},
        "veg_day1": {"ing_veg1"},
        "soup_day0": {"ing_soup_repeat"},
        "soup_day1_blocked": {"ing_soup_repeat"},
        "fruit_day0": {"ing_fruit0"},
        "fruit_day1": {"ing_fruit1"},
    }

    plan_days, _score, explanations, errors = fill_days_after_mains(
        horizon_days=2,
        main_ids=mains,
        sides=sides,
        vegs=vegs,
        soups=soups,
        fruits=fruits,
        feat=feat,
        hard=hard,
        weights=weights,
        soft=soft,
        dish_ingredient_ids=dish_ingredient_ids,
        start_date=date(2026, 5, 1),
    )

    assert len(plan_days) == 2
    assert plan_days[1].soup == ""
    assert plan_days[1].fruit
    assert len(plan_days[1].sides) == 2
    assert errors and errors[0]["code"] == "SOUP_NO_SOLUTION"
    assert explanations[1]["failed"] is True
    assert explanations[1]["reason_code"] == "SOUP_NO_SOLUTION"
