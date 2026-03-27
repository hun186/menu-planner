# src/menu_planner/api/export_excel.py
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Dict, Tuple

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

LABEL_MAP = {
    "near_expiry_bonus": "使用近到期食材（加分）",
    "use_inventory_bonus_main": "主菜使用庫存（加分）",
    "use_inventory_bonus_others": "湯/配菜使用庫存（加分）",
    "cost_over_max": "成本超過上限（扣分）",
    "cost_under_min": "成本低於下限（扣分）",
    "consecutive_same_meat": "連續同肉（扣分）",
    "cuisine_consecutive": "連續同菜系（扣分）",
}

DAILY_SUBTOTAL_FILL = PatternFill(fill_type="solid", fgColor="FFFDE68A")
WEEKLY_SUBTOTAL_FILL = PatternFill(fill_type="solid", fgColor="FFBFDBFE")
DAILY_SUBTOTAL_FONT = Font(color="FF92400E", bold=True)
WEEKLY_SUBTOTAL_FONT = Font(color="FF1E3A8A", bold=True)

def _num(x, default=0.0) -> float:
    try:
        return float(x)
    except Exception:
        return float(default)

def build_human_breakdown(day: Dict[str, Any]) -> str:
    """
    回傳一段可讀文字（含今日小結 + 拆解排序）。
    依賴 explain.py 透傳的：
      - score_summary {bonus, penalty, raw, fitness}
      - score_breakdown
      - items[*].near_expiry_days_min / inventory_hit_ratio / name
    """
    sd = day.get("score_summary") or {}
    bonus = _num(sd.get("bonus"), 0)
    penalty = _num(sd.get("penalty"), 0)
    raw = sd.get("raw", day.get("score"))
    raw = _num(raw, 0)
    fitness = sd.get("fitness", day.get("score_fitness"))
    fitness = _num(fitness, -raw)

    lines = []
    lines.append(f"今日小結：加分 {bonus:.2f} ／ 扣分 {penalty:.2f} ／ 原始 {raw:.2f}（符合度 {fitness:.2f}）")
    lines.append("打分拆解（影響大 → 小）")

    breakdown = day.get("score_breakdown") or {}
    items = day.get("items") or {}

    def near_expiry_list() -> str:
        cands = []
        # main/soup/sides（不含 fruit）
        for role in ("main", "soup"):
            di = items.get(role) or {}
            nd = di.get("near_expiry_days_min")
            if nd is not None and _num(nd, 999) <= 7:
                cands.append(f"{di.get('name','')}（{int(_num(nd))}天）")
        for s in (items.get("sides") or []):
            nd = s.get("near_expiry_days_min")
            if nd is not None and _num(nd, 999) <= 7:
                cands.append(f"{s.get('name','')}（{int(_num(nd))}天）")
        return "、".join(cands)

    def inv_main_hint() -> str:
        main = items.get("main") or {}
        r = main.get("inventory_hit_ratio")
        if isinstance(r, (int, float)):
            return f"主菜庫存命中 {r*100:.0f}%"
        return ""

    def inv_others_hint() -> str:
        ratios = []
        soup = items.get("soup") or {}
        r = soup.get("inventory_hit_ratio")
        if isinstance(r, (int, float)):
            ratios.append(r)
        for s in (items.get("sides") or []):
            r = s.get("inventory_hit_ratio")
            if isinstance(r, (int, float)):
                ratios.append(r)
        if ratios:
            pre = sum(ratios) * 100  # 加權前（score_day 內有 *0.5）
            return f"湯+配菜庫存命中合計 {pre:.0f}%（加權前）"
        return ""

    # 依影響絕對值排序
    for k, v in sorted(breakdown.items(), key=lambda kv: abs(_num(kv[1], 0)), reverse=True):
        v = _num(v, 0)
        label = LABEL_MAP.get(k, k)
        kind = "加分" if v < 0 else "扣分"
        amt = abs(v)

        extra = ""
        if k == "near_expiry_bonus":
            s = near_expiry_list()
            if s:
                extra = f"（近到期：{s}）"
        elif k == "use_inventory_bonus_main":
            s = inv_main_hint()
            if s:
                extra = f"（{s}）"
        elif k == "use_inventory_bonus_others":
            s = inv_others_hint()
            if s:
                extra = f"（{s}）"

        lines.append(f"{label}{extra}\n{kind} {amt:.2f}")

    return "\n".join(lines)


def _set_col_width(ws, widths: Dict[int, float]) -> None:
    for col_idx, w in widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = w




def _append_procurement_sheet(wb: Workbook, result: Dict[str, Any]) -> None:
    ws = wb.create_sheet("採買明細")
    header = [
        "日期", "角色", "菜名", "食材", "每人用量", "人數", "需求量", "需求單位",
        "單價", "單價單位", "小計", "價格日期"
    ]
    ws.append(header)

    bold = Font(bold=True)
    for c in range(1, len(header) + 1):
        ws.cell(row=1, column=c).font = bold

    for day in (result.get("days") or []):
        procurement = day.get("procurement") or {}
        date_text = day.get("date", "")
        people = procurement.get("people", 250)
        for dish in (procurement.get("dishes") or []):
            role = dish.get("role", "")
            dish_name = dish.get("dish_name", "")
            for ing in (dish.get("ingredients") or []):
                ws.append([
                    date_text,
                    role,
                    dish_name,
                    ing.get("ingredient_name", ""),
                    ing.get("qty_per_person", ""),
                    people,
                    ing.get("qty_for_people", ""),
                    ing.get("qty_unit", ""),
                    ing.get("unit_price", ""),
                    ing.get("unit_price_unit", ""),
                    ing.get("line_total", ""),
                    ing.get("price_date", ""),
                ])

    ws.freeze_panes = "A2"
    _set_col_width(ws, {
        1: 12, 2: 10, 3: 20, 4: 18, 5: 12, 6: 8, 7: 12, 8: 10, 9: 10, 10: 12, 11: 10, 12: 12
    })


def _append_procurement_summary_sheet(wb: Workbook, result: Dict[str, Any]) -> None:
    ws = wb.create_sheet("採買彙總")
    header = ["週次", "日期", "食材", "單價", "單價單位", "總量", "需求單位", "總價格", "備註"]
    ws.append(header)
    bold = Font(bold=True)
    for c in range(1, len(header) + 1):
        ws.cell(row=1, column=c).font = bold

    grand_total = 0.0
    week_total = 0.0
    week_index = 1
    valid_days = [d for d in (result.get("days") or []) if d.get("procurement")]

    for day_idx, day in enumerate(valid_days):
        procurement = day.get("procurement") or {}
        date_text = day.get("date", "")
        people = procurement.get("people", "")
        agg: Dict[Tuple[str, str, str, float], Dict[str, Any]] = {}

        for dish in (procurement.get("dishes") or []):
            for ing in (dish.get("ingredients") or []):
                unit_price = _num(ing.get("unit_price"), 0.0)
                key = (
                    str(ing.get("ingredient_name", "")),
                    str(ing.get("qty_unit", "")),
                    str(ing.get("unit_price_unit", "")),
                    unit_price,
                )
                bucket = agg.setdefault(key, {"qty": 0.0, "total": 0.0})
                bucket["qty"] += _num(ing.get("qty_for_people"), 0.0)
                bucket["total"] += _num(ing.get("line_total"), 0.0)

        day_total = 0.0
        for (name, qty_unit, price_unit, unit_price), val in sorted(agg.items(), key=lambda kv: kv[0][0]):
            total = round(val["total"], 2)
            day_total += total
            ws.append([
                f"第{week_index}週",
                date_text,
                name,
                round(unit_price, 4) if unit_price else "",
                price_unit,
                round(val["qty"], 4),
                qty_unit,
                total,
                f"人數={people}",
            ])

        ws.append([f"第{week_index}週", date_text, "每日小計", "", "", "", "", round(day_total, 2), ""])
        daily_row = ws.max_row
        for c in range(1, len(header) + 1):
            cell = ws.cell(row=daily_row, column=c)
            cell.fill = DAILY_SUBTOTAL_FILL
            cell.font = DAILY_SUBTOTAL_FONT
        week_total += day_total
        grand_total += day_total

        week_done = ((day_idx + 1) % 7 == 0) or (day_idx == len(valid_days) - 1)
        if week_done:
            ws.append([f"第{week_index}週", "", "每週小計", "", "", "", "", round(week_total, 2), ""])
            weekly_row = ws.max_row
            for c in range(1, len(header) + 1):
                cell = ws.cell(row=weekly_row, column=c)
                cell.fill = WEEKLY_SUBTOTAL_FILL
                cell.font = WEEKLY_SUBTOTAL_FONT
            week_index += 1
            week_total = 0.0

    ws.append(["", "", "全部合計", "", "", "", "", round(grand_total, 2), ""])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:I{ws.max_row}"
    _set_col_width(ws, {1: 10, 2: 12, 3: 18, 4: 10, 5: 10, 6: 12, 7: 10, 8: 12, 9: 14})

def build_plan_workbook(cfg: Dict[str, Any], result: Dict[str, Any]) -> bytes:
    """
    result 格式：engine/explain.py build_explanations 的輸出
    """
    def to_float(v):
        try:
            if v is None or v == "":
                return None
            return float(v)
        except Exception:
            return None

    wb = Workbook()

    # --- Sheet 1: 菜單 ---
    ws = wb.active
    ws.title = "菜單"
    header = [
        "日期", "主菜", "配菜1", "配菜2", "配菜3", "湯", "水果",
        "成本", "符合度", "分數拆解(JSON)", "分數拆解(易讀)"
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
        veg = items.get("veg") or {}
        side_names = [x.get("name", "") for x in sides]
        if veg.get("name"):
            side_names.append(veg.get("name", ""))
        while len(side_names) < 3:
            side_names.append("")
    
        breakdown = d.get("score_breakdown") or {}
        breakdown_str = json.dumps(breakdown, ensure_ascii=False)
    
        # ✅ 符合度（正分、越高越好）
        fitness = d.get("score_fitness")
        if fitness is None and d.get("score") is not None:
            fitness = round(-float(d["score"]), 2)
    
        human = build_human_breakdown(d) if not d.get("failed") else ""
    
        ws.append([
            d.get("date", ""),
            main,
            side_names[0],
            side_names[1],
            side_names[2],
            soup,
            fruit,
            d.get("day_cost", ""),
            fitness if fitness is not None else "",
            breakdown_str,
            human
        ])

    # ===== totals for summary =====
    total_cost = 0.0
    total_fitness = 0.0
    fitness_count = 0
    
    for d in days:
        # 成本
        c = to_float(d.get("day_cost"))
        if c is not None:
            total_cost += c
    
        # 符合度：優先用 score_fitness，沒有就用 -score
        if d.get("failed"):
            continue  # 失敗日不納入符合度統計（你想納入也可以拿掉這行）
    
        f = to_float(d.get("score_fitness"))
        if f is None:
            sc = to_float(d.get("score"))
            if sc is not None:
                f = -sc
    
        if f is not None:
            total_fitness += f
            fitness_count += 1

    ws.freeze_panes = "A2"
    _set_col_width(ws, {
        1: 12, 2: 22, 3: 18, 4: 18, 5: 18, 6: 18, 7: 14,
        8: 10, 9: 10, 10: 48, 11: 60
    })

    wrap = Alignment(vertical="top", wrap_text=True)
    for r in range(2, ws.max_row + 1):
        ws.cell(row=r, column=11).alignment = wrap  # 分數拆解(易讀)
    

    # （可選）把「原始JSON」欄隱藏：第 10 欄 = J
    # ws.column_dimensions[get_column_letter(10)].hidden = True

    # --- Sheet 2: 摘要 ---
    ws2 = wb.create_sheet("摘要")
    s = result.get("summary", {}) or {}
    days_n = int(s.get("days") or len(days) or 0)

    ws2.append(["項目", "值"])
    ws2["A1"].font = bold
    ws2["B1"].font = bold

    ws2.append(["天數", days_n])
    ws2.append(["人數", int((cfg or {}).get("people", 250) or 250)])
    ws2.append(["總成本", round(total_cost, 2)])
    ws2.append(["平均/日", round(total_cost / max(days_n, 1), 2)])
    
    ws2.append(["總符合度", round(total_fitness, 2)])
    ws2.append(["平均符合度/日", round(total_fitness / max(fitness_count, 1), 2)])


    #（可選）保留原始總分數，方便你對照
    #ws2.append(["原始總分數(對照)", s.get("total_score", "")])

    # ✅ 給使用者一句話說明
    ws2.append(["說明", "符合度越高越好；若未提供 score_fitness，則使用 -原始分數 當符合度。"])

    _set_col_width(ws2, {1: 18, 2: 60})

    # --- Sheet 3: 設定 ---
    ws3 = wb.create_sheet("設定")
    ws3.append(["constraints.json"])
    ws3["A1"].font = bold
    cfg_str = json.dumps(cfg, ensure_ascii=False, indent=2)
    for line in cfg_str.splitlines():
        ws3.append([line])
    _set_col_width(ws3, {1: 110})

    _append_procurement_sheet(wb, result)
    _append_procurement_summary_sheet(wb, result)

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()



def build_filename(prefix: str = "menu_plan") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.xlsx"
