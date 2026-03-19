from datetime import date

from src.menu_planner.engine.constraints import (
    PlanDay,
    _fixed_main_allowed_meats,
    check_ingredient_window_repeat,
    check_main_hard,
    check_side_window_repeat,
    check_veg_window_repeat,
)


def test_fixed_main_allowed_meats_supports_str_and_list_keys():
    hard = {
        "fixed_main_meat_by_weekday": {
            "1": "chicken",  # Monday
            2: ["pork", "beef"],  # Tuesday
        }
    }
    start = date(2026, 3, 16)  # Monday

    assert _fixed_main_allowed_meats(0, hard, start) == {"chicken"}
    assert _fixed_main_allowed_meats(1, hard, start) == {"pork", "beef"}
    assert _fixed_main_allowed_meats(2, hard, start) is None


def test_check_main_hard_reserves_future_fixed_quota_in_same_week():
    start = date(2026, 3, 16)  # Monday
    hard = {
        "weekly_max_main_meat": {"noodles": 1},
        "fixed_main_meat_by_weekday": {"3": "noodles"},  # Wednesday fixed
    }

    # Monday choosing noodles should be blocked because Wednesday is fixed noodles.
    ok = check_main_hard(
        day_idx=0,
        main_id="m-noodles",
        main_meat_type="noodles",
        plan_main_ids=[],
        plan_main_meats=[],
        weekly_meat_counts={0: {"noodles": 0}},
        hard=hard,
        start_date=start,
    )

    assert ok is False


def test_check_main_hard_allows_fixed_day_even_with_quota():
    start = date(2026, 3, 16)  # Monday
    hard = {
        "weekly_max_main_meat": {"noodles": 1},
        "fixed_main_meat_by_weekday": {"3": "noodles"},
    }

    # On Wednesday itself, one noodles slot is still allowed.
    ok = check_main_hard(
        day_idx=2,
        main_id="m-noodles",
        main_meat_type="noodles",
        plan_main_ids=["m1", "m2"],
        plan_main_meats=["chicken", "pork"],
        weekly_meat_counts={0: {"noodles": 0}},
        hard=hard,
        start_date=start,
    )

    assert ok is True


def test_check_side_window_repeat_skips_offdays():
    plan_days = [
        PlanDay(main="main-1", sides=["s1", "s2"], veg="v1", soup="sp1", fruit="f1"),
        PlanDay(main="", sides=[], veg="", soup="", fruit=""),  # offday
        PlanDay(main="main-2", sides=["s1", "s4"], veg="v2", soup="sp2", fruit="f2"),
    ]

    # Only active days count, so s1 has appeared twice already.
    assert check_side_window_repeat(3, ["s1", "s6"], plan_days, max_repeat_in_7=2) is False
    assert check_side_window_repeat(3, ["s8", "s6"], plan_days, max_repeat_in_7=2) is True


def test_check_veg_window_repeat_skips_offdays():
    plan_days = [
        PlanDay(main="main-1", sides=["s1", "s2"], veg="v1", soup="sp1", fruit="f1"),
        PlanDay(main="", sides=[], veg="", soup="", fruit=""),
        PlanDay(main="main-2", sides=["s1", "s4"], veg="v1", soup="sp2", fruit="f2"),
    ]

    assert check_veg_window_repeat(3, "v1", plan_days, max_repeat_in_7=2) is False
    assert check_veg_window_repeat(3, "v3", plan_days, max_repeat_in_7=2) is True


def test_check_ingredient_window_repeat_blocks_fourth_day_occurrence():
    plan_days = [
        PlanDay(main="m1", sides=["s1", "s2"], veg="v1", soup="sp1", fruit="f1"),
        PlanDay(main="m2", sides=["s3", "s4"], veg="v2", soup="sp2", fruit="f2"),
        PlanDay(main="m3", sides=["s5", "s6"], veg="v3", soup="sp3", fruit="f3"),
    ]
    dish_ingredient_ids = {
        "m1": {"ing_chicken"},
        "m2": {"ing_pork"},
        "m3": {"ing_beef"},
        "s1": {"ing_tofu"},
        "s3": {"ing_tofu"},
        "sp3": {"ing_tofu"},
        "s2": {"ing_cabbage"},
        "s4": {"ing_bokchoy"},
        "s5": {"ing_carrot"},
        "s6": {"ing_egg"},
        "v1": {"ing_spinach"},
        "v2": {"ing_bean"},
        "v3": {"ing_choy"},
        "sp1": {"ing_daikon"},
        "sp2": {"ing_tomato"},
        "f1": {"ing_apple"},
        "f2": {"ing_orange"},
        "f3": {"ing_banana"},
        "new_soup": {"ing_tofu"},
    }

    ok = check_ingredient_window_repeat(
        day_idx=3,
        dish_ids_today=["m4", "new_soup", "f4", "v4", "s7", "s8"],
        plan_days=plan_days,
        dish_ingredient_ids=dish_ingredient_ids,
        max_repeat_in_7=3,
    )
    assert ok is False


def test_check_ingredient_window_repeat_counts_once_per_day():
    plan_days = [
        PlanDay(main="m1", sides=["s1", "s2"], veg="v1", soup="sp1", fruit="f1"),
    ]
    dish_ingredient_ids = {
        "m1": {"ing_tofu"},
        "s1": {"ing_tofu"},
        "s2": {"ing_tofu"},
        "v1": {"ing_cabbage"},
        "sp1": {"ing_tomato"},
        "f1": {"ing_apple"},
        "m2": {"ing_pork"},
        "sp2": {"ing_tofu"},
    }

    ok = check_ingredient_window_repeat(
        day_idx=1,
        dish_ids_today=["m2", "sp2"],
        plan_days=plan_days,
        dish_ingredient_ids=dish_ingredient_ids,
        max_repeat_in_7=1,
    )
    # 前一天雖有多道豆腐，仍只算 1 天；因此今天再出現豆腐就超限
    assert ok is False


def test_check_ingredient_window_repeat_blocks_third_consecutive_day_when_limit_two():
    plan_days = [
        PlanDay(main="m1", sides=["s1"], veg="v1", soup="sp1", fruit="f1"),
        PlanDay(main="m2", sides=["s2"], veg="v2", soup="sp2", fruit="f2"),
    ]
    dish_ingredient_ids = {
        "m1": {"ing_chicken"},
        "m2": {"ing_pork"},
        "s1": {"family:tofu"},
        "s2": {"family:tofu"},
        "v1": {"ing_cabbage"},
        "v2": {"ing_spinach"},
        "sp1": {"ing_tomato"},
        "sp2": {"ing_daikon"},
        "f1": {"ing_apple"},
        "f2": {"ing_orange"},
        "s3": {"family:tofu"},
    }

    ok = check_ingredient_window_repeat(
        day_idx=2,
        dish_ids_today=["m3", "s3", "v3", "sp3", "f3"],
        plan_days=plan_days,
        dish_ingredient_ids=dish_ingredient_ids,
        max_repeat_in_7=7,
        max_consecutive_days=2,
    )
    assert ok is False


def test_check_ingredient_window_repeat_blocks_same_family_within_day_when_configured():
    plan_days = []
    dish_ingredient_ids = {
        "main": {"ing_chicken"},
        "side_tofu": {"family:tofu"},
        "soup_tofu": {"family:tofu"},
    }

    ok = check_ingredient_window_repeat(
        day_idx=0,
        dish_ids_today=["main", "side_tofu", "soup_tofu"],
        plan_days=plan_days,
        dish_ingredient_ids=dish_ingredient_ids,
        max_repeat_in_7=7,
        max_consecutive_days=7,
        no_same_within_day_keys={"family:tofu"},
    )
    assert ok is False


def test_check_ingredient_window_repeat_does_not_block_seasoning_when_only_tofu_family_limited():
    plan_days = []
    dish_ingredient_ids = {
        "main": {"ing_chicken", "ing_sugar"},
        "soup": {"ing_sugar", "ing_ginger"},
    }

    ok = check_ingredient_window_repeat(
        day_idx=0,
        dish_ids_today=["main", "soup"],
        plan_days=plan_days,
        dish_ingredient_ids=dish_ingredient_ids,
        max_repeat_in_7=7,
        max_consecutive_days=7,
        no_same_within_day_keys={"family:tofu"},
    )
    assert ok is True
