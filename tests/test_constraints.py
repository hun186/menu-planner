from datetime import date

from src.menu_planner.engine.constraints import (
    PlanDay,
    _fixed_main_allowed_meats,
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
