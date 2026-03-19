from src.menu_planner.db.repo import Dish
from src.menu_planner.engine.features import DishFeatures
from src.menu_planner.engine.planner import (
    _auto_relax_main_repeat_limit,
    _bump_soup_constraints_for_retry,
    _max_active_days_in_window,
)


def _mk_main(idx: int, meat: str = "chicken") -> Dish:
    return Dish(
        id=f"m{idx}",
        name=f"main-{idx}",
        role="main",
        cuisine="taiwanese",
        meat_type=meat,
        tags=[],
    )


def _mk_feat(dish_id: str, meat: str = "chicken") -> DishFeatures:
    return DishFeatures(
        dish_id=dish_id,
        role="main",
        meat_type=meat,
        cuisine="taiwanese",
        cost_per_serving=10.0,
        inventory_hit_ratio=0.0,
        near_expiry_days_min=None,
        used_inventory_ingredients=[],
    )


def test_max_active_days_in_window_caps_to_window_size():
    active_mask = [True] * 40
    assert _max_active_days_in_window(active_mask, window_days=30) == 30


def test_auto_relax_repeat_limit_only_when_required():
    mains = [_mk_main(i) for i in range(6)]
    feat = {d.id: _mk_feat(d.id) for d in mains}
    hard = {
        "repeat_limits": {"max_same_main_in_30_days": 1},
        "allowed_main_meat_types": ["chicken"],
    }
    active_mask = [True] * 10  # 30 日內 10 個供餐日、6 道主菜 => 至少要 2 次

    changed = _auto_relax_main_repeat_limit(hard, active_mask, mains, feat)

    assert changed["max_same_main_in_30_days"]["from"] == 1
    assert changed["max_same_main_in_30_days"]["to"] == 2
    assert hard["repeat_limits"]["max_same_main_in_30_days"] == 2


def test_auto_relax_respects_filters_and_keeps_limit_when_feasible():
    mains = [_mk_main(1, "chicken"), _mk_main(2, "pork"), _mk_main(3, "beef")]
    feat = {
        "m1": _mk_feat("m1", "chicken"),
        "m2": _mk_feat("m2", "pork"),
        "m3": _mk_feat("m3", "beef"),
    }
    hard = {
        "repeat_limits": {"max_same_main_in_30_days": 1},
        "allowed_main_meat_types": ["chicken", "pork", "beef"],
        "exclude_dish_ids": ["m3"],
    }
    active_mask = [True, True]  # 可用主菜 2 道，限制 1 已可行

    changed = _auto_relax_main_repeat_limit(hard, active_mask, mains, feat)

    assert changed == {}
    assert hard["repeat_limits"]["max_same_main_in_30_days"] == 1


def test_bump_soup_constraints_prefers_ingredient_limit_first():
    hard = {"repeat_limits": {"max_same_soup_in_7_days": 1, "max_same_ingredient_in_window_days": 3}}

    changed = _bump_soup_constraints_for_retry(hard)

    assert changed["max_same_ingredient_in_window_days"]["from"] == 3
    assert changed["max_same_ingredient_in_window_days"]["to"] == 4
    assert hard["repeat_limits"]["max_same_ingredient_in_window_days"] == 4
    assert hard["repeat_limits"]["max_same_soup_in_7_days"] == 1


def test_bump_soup_constraints_then_relaxes_soup_limit():
    hard = {"repeat_limits": {"max_same_soup_in_7_days": 1, "max_same_ingredient_in_window_days": 7}}

    changed = _bump_soup_constraints_for_retry(hard)

    assert changed["max_same_soup_in_7_days"]["from"] == 1
    assert changed["max_same_soup_in_7_days"]["to"] == 2
    assert hard["repeat_limits"]["max_same_soup_in_7_days"] == 2
