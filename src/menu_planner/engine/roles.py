# src/menu_planner/engine/roles.py
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

ROLE_ORDER = ("main", "noodle", "side", "veg", "soup", "fruit")
DEFAULT_ROLE_COUNTS = {"main": 1, "noodle": 0, "side": 2, "veg": 1, "soup": 1, "fruit": 1}


def _as_nonnegative_int(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return fallback


def normalize_role_counts(value: Any, fallback: Dict[str, int] | None = None) -> Dict[str, int]:
    base = dict(fallback or DEFAULT_ROLE_COUNTS)
    if isinstance(value, dict):
        for role in ROLE_ORDER:
            if role in value:
                base[role] = _as_nonnegative_int(value.get(role), base.get(role, 0))
    for role in ROLE_ORDER:
        base.setdefault(role, 0)
    return base


def counts_for_weekday(cfg: Dict[str, Any], weekday: int) -> Dict[str, int]:
    base = normalize_role_counts(cfg.get("per_day_roles"))
    overrides = cfg.get("per_weekday_roles") or {}
    rule = None
    if isinstance(overrides, dict):
        rule = overrides.get(weekday) or overrides.get(str(weekday))
    return normalize_role_counts(rule, fallback=base)


def counts_for_day(cfg: Dict[str, Any], start_date: date, day_idx: int) -> Dict[str, int]:
    return counts_for_weekday(cfg, (start_date + timedelta(days=day_idx)).isoweekday())


def has_any_role(counts: Dict[str, int]) -> bool:
    return any(int(counts.get(role, 0) or 0) > 0 for role in ROLE_ORDER)


def legacy_main_noodle_as_noodle(role: str, meat_type: str | None) -> str:
    if role == "main" and str(meat_type or "").strip().lower() == "noodles":
        return "noodle"
    return role
