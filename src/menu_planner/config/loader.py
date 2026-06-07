# src/menu_planner/config/loader.py
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_MEAT_TYPES = {"chicken", "pork", "beef", "fish", "seafood", "noodles", "vegetarian"}
ALLOWED_ROLES = {"main", "noodle", "side", "veg", "soup", "fruit"}


def load_defaults() -> Dict[str, Any]:
    p = Path(__file__).resolve().parent / "defaults.json"
    return json.loads(p.read_text(encoding="utf-8"))


def validate_config(cfg: Dict[str, Any]) -> Tuple[bool, List[str]]:
    errs: List[str] = []

    if "horizon_days" not in cfg:
        errs.append("缺少 horizon_days")
    else:
        try:
            if int(cfg["horizon_days"]) <= 0:
                errs.append("horizon_days 必須 > 0")
        except Exception:
            errs.append("horizon_days 必須是整數")

    schedule = cfg.get("schedule", {}) or {}
    weekdays = schedule.get("weekdays")
    if weekdays is not None:
        if not isinstance(weekdays, list):
            errs.append("schedule.weekdays 必須是陣列")
        else:
            bad = []
            for x in weekdays:
                try:
                    wd = int(x)
                except Exception:
                    bad.append(x)
                    continue
                if wd < 1 or wd > 7:
                    bad.append(x)
            if bad:
                errs.append(f"schedule.weekdays 僅支援 1~7：{bad}")

    for key in ["force_include_dates", "force_exclude_dates"]:
        vv = schedule.get(key)
        if vv is None:
            continue
        if not isinstance(vv, list):
            errs.append(f"schedule.{key} 必須是陣列")
            continue
        bad_dates = []
        for x in vv:
            ds = str(x).strip()
            try:
                datetime.strptime(ds, "%Y-%m-%d")
            except Exception:
                bad_dates.append(x)
        if bad_dates:
            errs.append(f"schedule.{key} 日期格式需為 YYYY-MM-DD：{bad_dates}")


    def _validate_role_counts(path: str, value):
        if value is None:
            return
        if not isinstance(value, dict):
            errs.append(f"{path} 必須是物件（role -> 非負整數）")
            return
        for role, count in value.items():
            if role not in ALLOWED_ROLES:
                errs.append(f"{path} 含不支援角色：{role}")
                continue
            try:
                if int(count) < 0:
                    errs.append(f"{path}.{role} 必須 >= 0")
            except Exception:
                errs.append(f"{path}.{role} 必須是整數")

    _validate_role_counts("per_day_roles", cfg.get("per_day_roles"))

    def _validate_nonnegative_int(path: str, value):
        try:
            if int(value) < 0:
                errs.append(f"{path} 必須 >= 0")
        except Exception:
            errs.append(f"{path} 必須是整數")

    _validate_nonnegative_int("prep_time_limit_minutes", cfg.get("prep_time_limit_minutes", 90))
    _validate_nonnegative_int("side_soup_protein_limit", cfg.get("side_soup_protein_limit", 2))
    per_weekday_prep = cfg.get("per_weekday_prep_time_limit_minutes")
    if per_weekday_prep is not None:
        if not isinstance(per_weekday_prep, dict):
            errs.append("per_weekday_prep_time_limit_minutes 必須是物件（weekday -> 非負整數分鐘）")
        else:
            for weekday, minutes in per_weekday_prep.items():
                try:
                    wd = int(weekday)
                except Exception:
                    errs.append(f"per_weekday_prep_time_limit_minutes 僅支援 1~7：{weekday}")
                    continue
                if wd < 1 or wd > 7:
                    errs.append(f"per_weekday_prep_time_limit_minutes 僅支援 1~7：{weekday}")
                    continue
                _validate_nonnegative_int(f"per_weekday_prep_time_limit_minutes.{weekday}", minutes)
    per_weekday_protein = cfg.get("per_weekday_side_soup_protein_limit")
    if per_weekday_protein is not None:
        if not isinstance(per_weekday_protein, dict):
            errs.append("per_weekday_side_soup_protein_limit 必須是物件（weekday -> 非負整數）")
        else:
            for weekday, limit in per_weekday_protein.items():
                try:
                    wd = int(weekday)
                except Exception:
                    errs.append(f"per_weekday_side_soup_protein_limit 僅支援 1~7：{weekday}")
                    continue
                if wd < 1 or wd > 7:
                    errs.append(f"per_weekday_side_soup_protein_limit 僅支援 1~7：{weekday}")
                    continue
                _validate_nonnegative_int(f"per_weekday_side_soup_protein_limit.{weekday}", limit)

    per_weekday_roles = cfg.get("per_weekday_roles")
    if per_weekday_roles is not None:
        if not isinstance(per_weekday_roles, dict):
            errs.append("per_weekday_roles 必須是物件（weekday -> role counts）")
        else:
            for weekday, counts in per_weekday_roles.items():
                try:
                    wd = int(weekday)
                except Exception:
                    errs.append(f"per_weekday_roles 僅支援 1~7：{weekday}")
                    continue
                if wd < 1 or wd > 7:
                    errs.append(f"per_weekday_roles 僅支援 1~7：{weekday}")
                    continue
                _validate_role_counts(f"per_weekday_roles.{weekday}", counts)

    hard = cfg.get("hard", {}) or {}
    allowed = hard.get("allowed_main_meat_types", [])
    if allowed:
        bad = [x for x in allowed if x not in ALLOWED_MEAT_TYPES]
        if bad:
            errs.append(f"allowed_main_meat_types 含不支援值：{bad}")

    cr = hard.get("cost_range_per_person_per_day")
    if cr:
        if "min" in cr and "max" in cr:
            try:
                if float(cr["min"]) > float(cr["max"]):
                    errs.append("cost_range min 不能大於 max")
            except Exception:
                errs.append("cost_range min/max 必須是數字")

    rep = hard.get("repeat_limits", {}) or {}
    for k in [
        "max_same_main_in_30_days",
        "max_same_side_in_7_days",
        "max_same_soup_in_7_days",
        "max_same_ingredient_in_7_days",
        "max_same_ingredient_in_window_days",
        "ingredient_repeat_window_days",
        "max_consecutive_ingredient_days",
    ]:
        if k in rep:
            try:
                if int(rep[k]) < 1:
                    errs.append(f"{k} 必須 >= 1")
            except Exception:
                errs.append(f"{k} 必須是整數")


    dish_allowed_weekdays = hard.get("dish_allowed_weekdays")
    if dish_allowed_weekdays is not None:
        if not isinstance(dish_allowed_weekdays, dict):
            errs.append("hard.dish_allowed_weekdays 必須是物件（dish_id -> 週幾陣列）")
        else:
            for dish_id, weekdays in dish_allowed_weekdays.items():
                if not isinstance(dish_id, str) or not dish_id.strip():
                    errs.append("hard.dish_allowed_weekdays 的 key 需為非空菜色 ID")
                    continue
                if not isinstance(weekdays, list):
                    errs.append(f"hard.dish_allowed_weekdays[{dish_id}] 必須是陣列")
                    continue
                bad = []
                for x in weekdays:
                    try:
                        wd = int(x)
                    except Exception:
                        bad.append(x)
                        continue
                    if wd < 1 or wd > 7:
                        bad.append(x)
                if bad:
                    errs.append(f"hard.dish_allowed_weekdays[{dish_id}] 僅支援 1~7：{bad}")

    no_same_family = hard.get("no_same_ingredient_family_within_day")
    if no_same_family is not None:
        if not isinstance(no_same_family, list):
            errs.append("no_same_ingredient_family_within_day 必須是陣列")
        else:
            bad = [x for x in no_same_family if not isinstance(x, str) or not x.strip()]
            if bad:
                errs.append("no_same_ingredient_family_within_day 需為非空字串陣列")

    return (len(errs) == 0), errs
