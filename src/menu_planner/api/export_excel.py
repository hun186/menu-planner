# src/menu_planner/api/export_excel.py
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Dict

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from .export_excel_breakdown import build_human_breakdown
from .export_excel_sheets import (
    append_config_sheet,
    append_procurement_sheet,
    append_procurement_summary_sheet,
    append_summary_sheet,
    set_col_width,
)


def _to_float_or_none(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _extract_menu_row(day: Dict[str, Any]) -> list[Any]:
    items = day.get("items", {}) or {}
    main = (items.get("main") or {}).get("name", "")
    soup = (items.get("soup") or {}).get("name", "")
    fruit = (items.get("fruit") or {}).get("name", "")

    sides = items.get("sides") or []
    veg = items.get("veg") or {}
    side_names = [x.get("name", "") for x in sides]
    if veg.get("name"):
        side_names.append(veg.get("name", ""))
    while len(side_names) < 3:
        side_names.append("")

    breakdown = day.get("score_breakdown") or {}
    breakdown_str = json.dumps(breakdown, ensure_ascii=False)

    fitness = day.get("score_fitness")
    if fitness is None and day.get("score") is not None:
        fitness = round(-float(day["score"]), 2)

    human = build_human_breakdown(day) if not day.get("failed") else ""
    return [
        day.get("date", ""),
        main,
        side_names[0],
        side_names[1],
        side_names[2],
        soup,
        fruit,
        day.get("day_cost", ""),
        fitness if fitness is not None else "",
        breakdown_str,
        human,
    ]


def _compute_plan_totals(days: list[Dict[str, Any]]) -> tuple[float, float, int]:
    total_cost = 0.0
    total_fitness = 0.0
    fitness_count = 0

    for day in days:
        cost = _to_float_or_none(day.get("day_cost"))
        if cost is not None:
            total_cost += cost

        if day.get("failed"):
            continue

        fitness = _to_float_or_none(day.get("score_fitness"))
        if fitness is None:
            raw_score = _to_float_or_none(day.get("score"))
            if raw_score is not None:
                fitness = -raw_score

        if fitness is not None:
            total_fitness += fitness
            fitness_count += 1

    return total_cost, total_fitness, fitness_count


def build_plan_workbook(cfg: Dict[str, Any], result: Dict[str, Any]) -> bytes:
    """
    result 格式：engine/explain.py build_explanations 的輸出
    """
    wb = Workbook()

    ws = wb.active
    ws.title = "菜單"
    header = [
        "日期",
        "主菜",
        "配菜1",
        "配菜2",
        "配菜3",
        "湯",
        "水果",
        "成本",
        "符合度",
        "分數拆解(JSON)",
        "分數拆解(易讀)",
    ]
    ws.append(header)

    bold = Font(bold=True)
    for col in range(1, len(header) + 1):
        cell = ws.cell(row=1, column=col)
        cell.font = bold
        cell.alignment = Alignment(vertical="center")

    days = result.get("days", []) or []
    for day in days:
        ws.append(_extract_menu_row(day))

    total_cost, total_fitness, fitness_count = _compute_plan_totals(days)

    ws.freeze_panes = "A2"
    set_col_width(ws, {1: 12, 2: 22, 3: 18, 4: 18, 5: 18, 6: 18, 7: 14, 8: 10, 9: 10, 10: 48, 11: 60})

    wrap = Alignment(vertical="top", wrap_text=True)
    for row in range(2, ws.max_row + 1):
        ws.cell(row=row, column=11).alignment = wrap

    append_summary_sheet(wb, cfg, result, days, total_cost, total_fitness, fitness_count)
    append_config_sheet(wb, cfg)
    append_procurement_sheet(wb, result)
    append_procurement_summary_sheet(wb, result)

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()



def build_filename(prefix: str = "menu_plan") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.xlsx"
