from src.menu_planner.db.repo import Dish
from src.menu_planner.engine.backtracking import _analyze_soup_rejections
from src.menu_planner.engine.constraints import PlanDay
from src.menu_planner.engine.features import DishFeatures


def _mk_soup(dish_id: str) -> Dish:
    return Dish(
        id=dish_id,
        name=dish_id,
        role="soup",
        cuisine="taiwanese",
        meat_type=None,
        tags=[],
    )


def _mk_feat(dish_id: str) -> DishFeatures:
    return DishFeatures(
        dish_id=dish_id,
        role="soup",
        meat_type=None,
        cuisine="taiwanese",
        cost_per_serving=10.0,
        inventory_hit_ratio=0.0,
        near_expiry_days_min=None,
        used_inventory_ingredients=[],
    )


def test_analyze_soup_rejections_reports_ingredient_and_repeat_blocks():
    soups = [_mk_soup("soup_repeat"), _mk_soup("soup_ing_block"), _mk_soup("soup_ok")]
    feat = {d.id: _mk_feat(d.id) for d in soups}
    plan_days = [
        PlanDay(main="m1", sides=["s1"], veg="v1", soup="soup_other", fruit="f1"),
        PlanDay(main="m3", sides=["s2"], veg="v2", soup="soup_repeat", fruit="f2"),
    ]
    dish_ingredient_ids = {
        "m1": {"ing_chicken"},
        "m3": {"ing_beef"},
        "m2": {"ing_pork"},
        "s1": {"ing_tofu"},
        "s2": {"ing_tofu"},
        "v1": {"ing_bokchoy"},
        "v2": {"ing_bokchoy2"},
        "f1": {"ing_apple"},
        "f2": {"ing_orange"},
        "soup_other": {"ing_radish"},
        "soup_repeat": {"ing_tomato"},
        "soup_ing_block": {"ing_tofu"},
        "soup_ok": {"ing_egg"},
    }
    hard = {
        "repeat_limits": {
            "max_same_soup_in_7_days": 1,
            "max_same_ingredient_in_window_days": 2,
        }
    }

    stats = _analyze_soup_rejections(
        day_idx=2,
        soups=soups,
        plan_days=plan_days,
        feat=feat,
        hard=hard,
        main_id="m2",
        dish_ingredient_ids=dish_ingredient_ids,
    )

    assert stats["candidate_count"] == 3
    assert stats["feasible_count"] == 1
    assert stats["blocked_by_soup_repeat"] == 1
    assert stats["blocked_by_ingredient_repeat"] == 1
    assert stats["max_same_ingredient_in_window_days"] == 2
