# src/menu_planner/config/loader.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


ALLOWED_MEAT_TYPES = {"chicken", "pork", "beef", "fish", "seafood", "vegetarian"}
ALLOWED_ROLES = {"main", "side", "soup", "fruit"}


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
    for k in ["max_same_main_in_30_days", "max_same_side_in_7_days", "max_same_soup_in_7_days"]:
        if k in rep:
            try:
                if int(rep[k]) < 1:
                    errs.append(f"{k} 必須 >= 1")
            except Exception:
                errs.append(f"{k} 必須是整數")

    return (len(errs) == 0), errs
