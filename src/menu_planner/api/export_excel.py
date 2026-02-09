# src/menu_planner/api/export_excel.py
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Dict

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from openpyxl.utils import get_column_letter


def _set_col_width(ws, widths: Dict[int, float]) -> None:
    for col_idx, w in widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = w


def build_plan_workbook(cfg: Dict[str, Any], result: Dict[str, Any]) -> bytes:
    """
    result 格式：engine/explain.py build_explanations 的輸出
    """
    wb = Workbook()

    # --- Sheet 1: 菜單 ---
    ws = wb.active
    ws.title = "菜單"
    header = [
        "日期", "主菜", "配菜1", "配菜2", "配菜3", "湯", "水果",
        "成本", "分數", "分數拆解(JSON)"
    ]
    ws.append(header)

    bold = Font(bold=True)
    for c in range(1, len(header) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = bold
        cell.alignment = Alignment(vertical="center")

    days = result.get("days", []) or []
    for d in days:
        items = d.get("items", {}) or {}
        main = (items.get("main") or {}).get("name", "")
        soup = (items.get("soup") or {}).get("name", "")
        fruit = (items.get("fruit") or {}).get("name", "")

        sides = items.get("sides") or []
        side_names = [x.get("name", "") for x in sides]
        while len(side_names) < 3:
            side_names.append("")

        breakdown = d.get("score_breakdown") or {}
        breakdown_str = json.dumps(breakdown, ensure_ascii=False)

        ws.append([
            d.get("date", ""),
            main,
            side_names[0],
            side_names[1],
            side_names[2],
            soup,
            fruit,
            d.get("day_cost", ""),
            d.get("score", ""),
            breakdown_str
        ])

    ws.freeze_panes = "A2"
    _set_col_width(ws, {
        1: 12, 2: 22, 3: 18, 4: 18, 5: 18, 6: 18, 7: 14, 8: 10, 9: 10, 10: 48
    })

    # --- Sheet 2: 摘要 ---
    ws2 = wb.create_sheet("摘要")
    s = result.get("summary", {}) or {}
    ws2.append(["項目", "值"])
    ws2["A1"].font = bold
    ws2["B1"].font = bold
    ws2.append(["天數", s.get("days", "")])
    ws2.append(["總成本", s.get("total_cost", "")])
    ws2.append(["平均/日", s.get("avg_cost_per_day", "")])
    ws2.append(["總分數", s.get("total_score", "")])
    _set_col_width(ws2, {1: 14, 2: 20})

    # --- Sheet 3: 設定 ---
    ws3 = wb.create_sheet("設定")
    ws3.append(["constraints.json"])
    ws3["A1"].font = bold
    cfg_str = json.dumps(cfg, ensure_ascii=False, indent=2)
    # 直接放到多列（避免一格太長）
    for line in cfg_str.splitlines():
        ws3.append([line])
    _set_col_width(ws3, {1: 110})

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def build_filename(prefix: str = "menu_plan") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.xlsx"
