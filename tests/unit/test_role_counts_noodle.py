from datetime import date

from src.menu_planner.db.repo import Dish
from src.menu_planner.engine.backtracking import fill_days_after_mains, plan_mains_beam
from src.menu_planner.engine.constraints import PlanDay, check_noodle_window_repeat
from src.menu_planner.engine.features import DishFeatures
from src.menu_planner.engine.planner import _get_active_mask, _split_dishes_by_role
from src.menu_planner.engine.roles import counts_for_day


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


def test_default_weekday_role_counts_split_noodle_from_main():
    cfg = {
        "per_day_roles": {"main": 1, "noodle": 0, "side": 2, "veg": 1, "soup": 1, "fruit": 1},
        "per_weekday_roles": {"3": {"main": 1, "noodle": 1, "side": 1, "veg": 1, "soup": 1, "fruit": 1}},
        "schedule": {"weekdays": [1, 2, 3, 4, 5]},
    }
    monday = date(2026, 3, 2)

    assert counts_for_day(cfg, monday, 0)["noodle"] == 0
    assert counts_for_day(cfg, monday, 2)["noodle"] == 1
    assert counts_for_day(cfg, monday, 2)["main"] == 1
    assert _get_active_mask(monday, 5, cfg) == [True, True, True, True, True]

    main = _dish("main_chicken", "main", "chicken")
    legacy_noodle = _dish("legacy_noodle", "main", "noodles")
    explicit_noodle = _dish("explicit_noodle", "noodle")
    mains, _, _, _, _, noodles = _split_dishes_by_role([main, legacy_noodle, explicit_noodle])

    assert [d.id for d in mains] == ["main_chicken"]
    assert [d.id for d in noodles] == ["legacy_noodle", "explicit_noodle"]


def test_wednesday_can_plan_main_and_noodle_independently():
    cfg = {
        "per_day_roles": {"main": 1, "noodle": 0, "side": 2, "veg": 1, "soup": 1, "fruit": 1},
        "per_weekday_roles": {"3": {"main": 1, "noodle": 1, "side": 1, "veg": 1, "soup": 1, "fruit": 1}},
    }
    start = date(2026, 3, 2)  # Monday
    counts = [counts_for_day(cfg, start, i) for i in range(3)]
    dishes = [
        _dish("main_chicken", "main", "chicken"),
        _dish("main_pork", "main", "pork"),
        _dish("main_beef", "main", "beef"),
        _dish("noodle_a", "noodle"),
        _dish("side_a", "side"),
        _dish("side_b", "side"),
        _dish("side_c", "side"),
        _dish("veg_a", "veg"),
        _dish("soup_a", "soup"),
        _dish("fruit_a", "fruit"),
    ]
    feat = {d.id: _feat(d) for d in dishes}
    mains, sides, vegs, soups, fruits, noodles = _split_dishes_by_role(dishes)
    hard = {
        "allowed_main_meat_types": ["chicken", "pork", "beef"],
        "no_consecutive_same_main_meat": False,
        "weekly_max_main_meat": {},
        "repeat_limits": {"max_same_main_in_30_days": 99, "max_same_side_in_7_days": 99, "max_same_soup_in_7_days": 99, "max_same_fruit_in_7_days": 99, "max_same_ingredient_in_window_days": 99},
        "cost_range_per_person_per_day": {"min": 0, "max": 99},
    }
    main_ids = plan_mains_beam(3, mains, feat, hard, 4, 10, seed=1, start_date=start, active_mask=[True] * 3, role_counts_by_day=counts)
    plan, _, _, errors = fill_days_after_mains(
        3,
        main_ids,
        sides,
        vegs,
        soups,
        fruits,
        feat,
        hard,
        {},
        {},
        start_date=start,
        active_mask=[True] * 3,
        role_counts_by_day=counts,
        noodles=noodles,
    )

    assert not errors
    assert plan[0].main and not plan[0].noodle
    assert len(plan[0].mains) == 1
    assert plan[1].main and not plan[1].noodle
    assert len(plan[1].mains) == 1
    assert plan[2].main and plan[2].noodle == "noodle_a"
    assert len(plan[2].mains) == 1
    assert len(plan[2].noodles) == 1
    assert len(plan[2].sides) == 1


def test_fill_days_honors_multi_count_for_all_roles():
    cfg = {
        "per_day_roles": {"main": 2, "noodle": 2, "side": 3, "veg": 2, "soup": 2, "fruit": 2},
    }
    start = date(2026, 3, 2)
    counts = [counts_for_day(cfg, start, 0)]
    dishes = [
        *[_dish(f"main_{i}", "main", "chicken") for i in range(3)],
        *[_dish(f"noodle_{i}", "noodle") for i in range(2)],
        *[_dish(f"side_{i}", "side") for i in range(3)],
        *[_dish(f"veg_{i}", "veg") for i in range(2)],
        *[_dish(f"soup_{i}", "soup") for i in range(2)],
        *[_dish(f"fruit_{i}", "fruit") for i in range(2)],
    ]
    feat = {d.id: _feat(d) for d in dishes}
    mains, sides, vegs, soups, fruits, noodles = _split_dishes_by_role(dishes)
    hard = {
        "allowed_main_meat_types": ["chicken"],
        "no_consecutive_same_main_meat": False,
        "weekly_max_main_meat": {},
        "repeat_limits": {
            "max_same_main_in_30_days": 99,
            "max_same_side_in_7_days": 99,
            "max_same_veg_in_7_days": 99,
            "max_same_soup_in_7_days": 99,
            "max_same_fruit_in_7_days": 99,
            "max_same_ingredient_in_window_days": 99,
        },
        "cost_range_per_person_per_day": {"min": 0, "max": 99},
    }

    main_ids = plan_mains_beam(
        1,
        mains,
        feat,
        hard,
        4,
        10,
        seed=1,
        start_date=start,
        active_mask=[True],
        role_counts_by_day=counts,
    )
    plan, _, _, errors = fill_days_after_mains(
        1,
        main_ids,
        sides,
        vegs,
        soups,
        fruits,
        feat,
        hard,
        {},
        {},
        start_date=start,
        active_mask=[True],
        role_counts_by_day=counts,
        noodles=noodles,
        mains=mains,
    )

    assert not errors
    day = plan[0]
    assert len(day.mains) == 2
    assert len(day.noodles) == 2
    assert len(day.sides) == 3
    assert len(day.vegs) == 2
    assert len(day.soups) == 2
    assert len(day.fruits) == 2


def test_noodle_repeat_limit_blocks_reuse_within_7_days():
    plan_days = [
        PlanDay(
            main="main_a",
            sides=["side_a"],
            veg="veg_a",
            soup="soup_a",
            fruit="fruit_a",
            noodle="noodle_a",
        )
    ]

    assert not check_noodle_window_repeat(
        1, ["noodle_a"], plan_days, max_repeat=1, window_days=7
    )
    assert check_noodle_window_repeat(
        1, ["noodle_b"], plan_days, max_repeat=1, window_days=7
    )


def test_noodle_repeat_limit_allows_weekly_wednesday_reuse():
    plan_days = [
        PlanDay(
            main="main_a",
            sides=["side_a"],
            veg="veg_a",
            soup="soup_a",
            fruit="fruit_a",
            noodle="noodle_a",
        ),
        *[
            PlanDay(
                main="main_b",
                sides=["side_b"],
                veg="veg_b",
                soup="soup_b",
                fruit="fruit_b",
            )
            for _ in range(6)
        ],
    ]

    assert check_noodle_window_repeat(
        7, ["noodle_a"], plan_days, max_repeat=1, window_days=7
    )


def test_noodle_30_day_repeat_limit_runs_independently_from_7_day_limit():
    plan_days = []
    for day_idx in range(20):
        noodle = "noodle_a" if day_idx in {0, 10} else ""
        plan_days.append(
            PlanDay(
                main="main_a",
                sides=["side_a"],
                veg="veg_a",
                soup="soup_a",
                fruit="fruit_a",
                noodle=noodle,
            )
        )

    assert check_noodle_window_repeat(
        20, ["noodle_a"], plan_days, max_repeat=1, window_days=7
    )
    assert not check_noodle_window_repeat(
        20, ["noodle_a"], plan_days, max_repeat=2, window_days=30
    )
