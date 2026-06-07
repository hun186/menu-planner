from __future__ import annotations

from typing import Any, Dict

from ..engine.roles import ROLE_LABELS, ROLE_ORDER, ROLE_PLURALS

LABEL_MAP = {
    "near_expiry_bonus": "使用近到期食材（加分）",
    "use_inventory_bonus_main": "主菜使用庫存（加分）",
    "use_inventory_bonus_others": "非主菜角色使用庫存（加分）",
    "cost_over_max": "成本超過上限（扣分）",
    "cost_under_min": "成本低於下限（扣分）",
    "consecutive_same_meat": "連續同肉（扣分）",
    "cuisine_consecutive": "連續同菜系（扣分）",
}


def num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _role_dishes(items: Dict[str, Any], role: str) -> list[Dict[str, Any]]:
    plural = ROLE_PLURALS[role]
    dishes = items.get(plural)
    if isinstance(dishes, list):
        filtered = [x for x in dishes if isinstance(x, dict) and (x.get("name") or x.get("id"))]
        if filtered:
            return filtered

    dish = items.get(role) or {}
    if isinstance(dish, dict) and (dish.get("name") or dish.get("id")):
        return [dish]
    return []


def _all_role_dishes(items: Dict[str, Any], roles: tuple[str, ...] = ROLE_ORDER) -> list[tuple[str, Dict[str, Any]]]:
    out: list[tuple[str, Dict[str, Any]]] = []
    for role in roles:
        for dish in _role_dishes(items, role):
            out.append((role, dish))
    return out


def _dish_label(role: str, dish: Dict[str, Any]) -> str:
    return str(dish.get("name") or dish.get("id") or ROLE_LABELS.get(role, role))


def build_human_breakdown(day: Dict[str, Any]) -> str:
    """
    回傳一段可讀文字（含今日小結 + 拆解排序）。
    依賴 explain.py 透傳的：
      - score_summary {bonus, penalty, raw, fitness}
      - score_breakdown
      - items[*].near_expiry_days_min / inventory_hit_ratio / name
    """
    score_summary = day.get("score_summary") or {}
    bonus = num(score_summary.get("bonus"), 0)
    penalty = num(score_summary.get("penalty"), 0)
    raw = num(score_summary.get("raw", day.get("score")), 0)
    fitness = num(score_summary.get("fitness", day.get("score_fitness")), -raw)

    lines = [
        f"今日小結：加分 {bonus:.2f} ／ 扣分 {penalty:.2f} ／ 原始 {raw:.2f}（目標匹配度 {fitness:.2f}）",
        "打分拆解（影響大 → 小）",
    ]

    items = day.get("items") or {}
    if not isinstance(items, dict):
        items = {}
    breakdown = day.get("score_breakdown") or {}

    def near_expiry_list() -> str:
        candidates: list[str] = []
        for role, dish_item in _all_role_dishes(items):
            near_expiry_days = dish_item.get("near_expiry_days_min")
            if near_expiry_days is not None and num(near_expiry_days, 999) <= 7:
                candidates.append(f"{_dish_label(role, dish_item)}（{int(num(near_expiry_days))}天）")
        return "、".join(candidates)

    def inv_role_hint(roles: tuple[str, ...]) -> str:
        candidates: list[str] = []
        for role, dish_item in _all_role_dishes(items, roles):
            ratio = dish_item.get("inventory_hit_ratio")
            if isinstance(ratio, (int, float)):
                candidates.append(f"{_dish_label(role, dish_item)} {ratio * 100:.0f}%")
        return "、".join(candidates)

    def inv_main_hint() -> str:
        hint = inv_role_hint(("main",))
        if hint:
            return f"主菜庫存命中：{hint}"
        return ""

    def inv_others_hint() -> str:
        other_roles = tuple(role for role in ROLE_ORDER if role != "main")
        hint = inv_role_hint(other_roles)
        if hint:
            return f"非主菜庫存命中：{hint}"
        return ""

    for key, value in sorted(breakdown.items(), key=lambda kv: abs(num(kv[1], 0)), reverse=True):
        score_value = num(value, 0)
        label = LABEL_MAP.get(key, key)
        kind = "加分" if score_value < 0 else "扣分"
        amount = abs(score_value)

        extra = ""
        if key == "near_expiry_bonus":
            near_expiry = near_expiry_list()
            if near_expiry:
                extra = f"（近到期：{near_expiry}）"
        elif key == "use_inventory_bonus_main":
            main_hint = inv_main_hint()
            if main_hint:
                extra = f"（{main_hint}）"
        elif key == "use_inventory_bonus_others":
            others_hint = inv_others_hint()
            if others_hint:
                extra = f"（{others_hint}）"

        lines.append(f"{label}{extra}\n{kind} {amount:.2f}")

    return "\n".join(lines)
