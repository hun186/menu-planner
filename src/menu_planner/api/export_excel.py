# src/menu_planner/api/export_excel.py
from __future__ import annotations

import io
import json
from datetime import datetime
from typing import Any, Dict

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
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
        side_names = [x.get("name", "") for x in sides]
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

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()



def build_filename(prefix: str = "menu_plan") -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{ts}.xlsx"
