from datetime import date

from src.menu_planner.config.loader import validate_config
from src.menu_planner.db.repo import Dish
from src.menu_planner.engine.backtracking import fill_days_after_mains, plan_mains_beam
from src.menu_planner.engine.constraints import PlanDay
from src.menu_planner.engine.features import DishFeatures
from src.menu_planner.engine.local_search import _hard_ok_for_plan


def _mk_dish(dish_id: str, role: str, meat_type: str | None = None) -> Dish:
    return Dish(
        id=dish_id,
        name=dish_id,
        role=role,
        cuisine="tw",
        meat_type=meat_type or ("chicken" if role == "main" else None),
        tags=[],
    )


def _mk_feat(dish_id: str, role: str, meat_type: str | None = None) -> DishFeatures:
    return DishFeatures(
        dish_id=dish_id,
        role=role,
        meat_type=meat_type or ("chicken" if role == "main" else None),
        cuisine="tw",
        cost_per_serving=1.0,
        inventory_hit_ratio=0.0,
        near_expiry_days_min=None,
        used_inventory_ingredients=[],
    )


def test_validate_config_accepts_dish_allowed_weekdays_mapping():
    ok, errors = validate_config({
        "horizon_days": 1,
        "hard": {"dish_allowed_weekdays": {"wing": [3]}},
    })

    assert ok
    assert errors == []


def test_validate_config_rejects_bad_dish_allowed_weekdays():
    ok, errors = validate_config({
        "horizon_days": 1,
        "hard": {"dish_allowed_weekdays": {"wing": [0, 8]}},
    })

    assert not ok
    assert any("hard.dish_allowed_weekdays[wing] 僅支援 1~7" in e for e in errors)


def test_plan_mains_beam_respects_configured_dish_allowed_weekdays():
    monday_only = _mk_dish("monday_main", "main")
    wednesday_only = _mk_dish("wednesday_main", "main")
    mains = [monday_only, wednesday_only]
    feat = {d.id: _mk_feat(d.id, "main", meat_type="chicken") for d in mains}
    hard = {
        "allowed_main_meat_types": ["chicken"],
        "dish_allowed_weekdays": {"monday_main": [1], "wednesday_main": [3]},
        "repeat_limits": {"max_same_main_in_30_days": 10},
    }

    main_ids = plan_mains_beam(
        horizon_days=3,
        mains=mains,
        feat=feat,
        hard=hard,
        beam_width=4,
        candidate_limit=10,
        seed=7,
        start_date=date(2026, 6, 1),  # Monday
        active_mask=[True, False, True],
    )

    assert main_ids == ["monday_main", "", "wednesday_main"]


def test_fill_days_after_mains_filters_non_main_roles_by_configured_weekdays():
    main_ids = ["main_a"]
    sides = [_mk_dish("side_allowed_a", "side"), _mk_dish("side_allowed_b", "side"), _mk_dish("side_blocked", "side")]
    vegs = [_mk_dish("veg_allowed", "veg")]
    soups = [_mk_dish("soup_allowed", "soup")]
    fruits = [_mk_dish("fruit_allowed", "fruit")]
    all_ids = ["main_a", "side_allowed_a", "side_allowed_b", "side_blocked", "veg_allowed", "soup_allowed", "fruit_allowed"]
    feat = {dish_id: _mk_feat(dish_id, "main" if dish_id == "main_a" else "side") for dish_id in all_ids}

    plan_days, _score, _explanations, errors = fill_days_after_mains(
        horizon_days=1,
        main_ids=main_ids,
        sides=sides,
        vegs=vegs,
        soups=soups,
        fruits=fruits,
        feat=feat,
        hard={
            "seed": 1,
            "dish_allowed_weekdays": {
                "side_allowed_a": [3],
                "side_allowed_b": [3],
                "side_blocked": [1],
                "veg_allowed": [3],
                "soup_allowed": [3],
                "fruit_allowed": [3],
            },
            "repeat_limits": {
                "max_same_side_in_7_days": 2,
                "max_same_soup_in_7_days": 2,
                "max_same_fruit_in_7_days": 2,
                "max_same_veg_in_7_days": 2,
            },
            "cost_range_per_person_per_day": {"min": 0, "max": 999},
        },
        weights={},
        soft={},
        start_date=date(2026, 6, 3),  # Wednesday
    )

    assert not errors
    assert set(plan_days[0].sides) == {"side_allowed_a", "side_allowed_b"}
    assert plan_days[0].veg == "veg_allowed"
    assert plan_days[0].soup == "soup_allowed"
    assert plan_days[0].fruit == "fruit_allowed"


def test_local_search_hard_check_rejects_configured_disallowed_weekday_dish():
    main = _mk_dish("main_a", "main")
    side_allowed_a = _mk_dish("side_allowed_a", "side")
    side_blocked = _mk_dish("side_blocked", "side")
    veg = _mk_dish("veg_allowed", "veg")
    soup = _mk_dish("soup_allowed", "soup")
    fruit = _mk_dish("fruit_allowed", "fruit")
    dishes = [main, side_allowed_a, side_blocked, veg, soup, fruit]
    feat = {d.id: _mk_feat(d.id, d.role, d.meat_type) for d in dishes}
    plan = [PlanDay(
        main="main_a",
        sides=["side_allowed_a", "side_blocked"],
        veg="veg_allowed",
        soup="soup_allowed",
        fruit="fruit_allowed",
    )]

    assert not _hard_ok_for_plan(
        plan,
        mains=[main],
        feat=feat,
        hard={
            "dish_allowed_weekdays": {"side_blocked": [1]},
            "repeat_limits": {"max_same_side_in_7_days": 2, "max_same_soup_in_7_days": 2},
        },
        start_date=date(2026, 6, 3),
        dish_by_id={d.id: d for d in dishes},
    )
