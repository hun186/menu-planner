from src.menu_planner.engine.features import DishFeatures
from src.menu_planner.engine.scoring import score_day


def _mk_dish(dish_id: str, used=None, expiry=None):
    return DishFeatures(
        dish_id=dish_id,
        role="main",
        meat_type="chicken",
        cuisine="tw",
        cost_per_serving=10.0,
        inventory_hit_ratio=1.0 if used else 0.0,
        near_expiry_days_min=0 if used else None,
        used_inventory_ingredients=used or [],
        ingredient_count=1,
        inventory_expiry_dates=expiry or {},
    )


def test_score_day_ignores_expired_inventory_after_plan_date():
    chosen = {
        "main": _mk_dish("m", used=["ing_taro"], expiry={"ing_taro": "2026-03-21"}),
        "soup": _mk_dish("s"),
        "side1": _mk_dish("a"),
        "side2": _mk_dish("b"),
        "veg": _mk_dish("v"),
        "fruit": _mk_dish("f"),
    }

    hard = {}
    weights = {"use_inventory_bonus": -10, "near_expiry_bonus": -12}

    before = score_day(
        day_cost=50,
        hard=hard,
        weights=weights,
        chosen=chosen,
        context={"prefer_use_inventory": True, "prefer_near_expiry": True, "plan_date": "2026-03-20"},
    )
    after = score_day(
        day_cost=50,
        hard=hard,
        weights=weights,
        chosen=chosen,
        context={"prefer_use_inventory": True, "prefer_near_expiry": True, "plan_date": "2026-03-22"},
    )

    assert before.items["use_inventory_bonus_main"] < 0
    assert before.items["near_expiry_bonus"] < 0
    assert after.items["use_inventory_bonus_main"] == 0
    assert after.items["near_expiry_bonus"] == 0


def test_near_expiry_bonus_starts_earlier_than_two_days():
    chosen = {
        "main": _mk_dish("m", used=["ing_taro"], expiry={"ing_taro": "2026-03-25"}),
        "soup": _mk_dish("s"),
        "side1": _mk_dish("a"),
        "side2": _mk_dish("b"),
        "veg": _mk_dish("v"),
        "fruit": _mk_dish("f"),
    }

    result = score_day(
        day_cost=50,
        hard={},
        weights={"near_expiry_bonus": -12},
        chosen=chosen,
        context={"prefer_near_expiry": True, "plan_date": "2026-03-21"},
    )

    # 2026-03-25 相對於 2026-03-21 還有 4 天，現在屬於高權重加分區間（0.8）
    assert result.items["near_expiry_bonus"] == -9.6
