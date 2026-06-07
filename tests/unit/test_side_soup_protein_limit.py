from datetime import date

from src.menu_planner.config.loader import validate_config
from src.menu_planner.db.repo import Dish
from src.menu_planner.engine.backtracking import fill_days_after_mains
from src.menu_planner.engine.features import DishFeatures


def _dish(did, role, meat=None):
    return Dish(id=did, name=did, role=role, cuisine="tw", meat_type=meat, tags=[])


def _feat(dish):
    return DishFeatures(
        dish_id=dish.id,
        role=dish.role,
        meat_type=dish.meat_type,
        cuisine=dish.cuisine,
        cost_per_serving=1.0,
        inventory_hit_ratio=0.0,
        near_expiry_days_min=None,
        used_inventory_ingredients=[],
    )


def _protein_count(day, dish_has_protein):
    return sum(1 for did in list(day.sides) + list(day.soups) if dish_has_protein.get(did, False))


def test_validate_config_accepts_global_and_weekday_side_soup_protein_limits():
    ok, errors = validate_config(
        {
            "horizon_days": 1,
            "side_soup_protein_limit": 2,
            "per_weekday_side_soup_protein_limit": {"2": 1},
        }
    )

    assert ok
    assert errors == []


def test_fill_days_honors_side_soup_protein_limit_and_weekday_override():
    start = date(2026, 6, 1)  # Monday; day index 1 is Tuesday override.
    dishes = [
        _dish("main_a", "main", "chicken"),
        _dish("soup_plain", "soup"),
        _dish("side_protein_a", "side"),
        _dish("side_protein_b", "side"),
        _dish("side_plain", "side"),
    ]
    feat = {d.id: _feat(d) for d in dishes}
    dish_has_protein = {
        "side_protein_a": True,
        "side_protein_b": True,
        "side_plain": False,
        "soup_plain": False,
    }
    hard = {
        "seed": 1,
        "side_soup_protein_limit": 2,
        "per_weekday_side_soup_protein_limit": {"2": 1},
        "repeat_limits": {
            "max_same_side_in_7_days": 99,
            "max_same_soup_in_7_days": 99,
            "max_same_ingredient_in_window_days": 99,
        },
        "cost_range_per_person_per_day": {"min": 0, "max": 999},
    }

    plan, _score, explanations, errors = fill_days_after_mains(
        horizon_days=2,
        main_ids=["main_a", "main_a"],
        sides=[d for d in dishes if d.role == "side"],
        vegs=[],
        soups=[d for d in dishes if d.role == "soup"],
        fruits=[],
        feat=feat,
        hard=hard,
        weights={},
        soft={},
        dish_has_protein=dish_has_protein,
        start_date=start,
        role_counts_by_day=[
            {"main": 1, "noodle": 0, "side": 2, "veg": 0, "soup": 1, "fruit": 0},
            {"main": 1, "noodle": 0, "side": 2, "veg": 0, "soup": 1, "fruit": 0},
        ],
        mains=[d for d in dishes if d.role == "main"],
    )

    assert errors == []
    assert _protein_count(plan[0], dish_has_protein) <= 2
    assert _protein_count(plan[1], dish_has_protein) <= 1
    assert explanations[0]["side_soup_protein_limit"] == 2
    assert explanations[1]["side_soup_protein_limit"] == 1
