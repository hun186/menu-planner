from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.menu_planner.config.loader import load_defaults
from src.menu_planner.engine.planner import plan_month
from src.menu_planner.api.export_excel import build_plan_workbook

DB_PATH = ROOT / "data" / "menu.db"
OUT_XLSX = ROOT / "data" / "menu_plan_360d.xlsx"
OUT_MD = ROOT / "docs" / "menu_plan_360_preview.md"


def format_items(day: dict) -> tuple[str, str, str, str]:
    items = day.get("items") or {}
    main = (items.get("main") or {}).get("name") or "-"
    sides = items.get("sides") or []
    side_names = "、".join([s.get("name") or "-" for s in sides]) if sides else "-"
    soup = (items.get("soup") or {}).get("name") or "-"
    fruit = (items.get("fruit") or {}).get("name") or "-"
    return main, side_names, soup, fruit


def build_preview_markdown(days: list[dict], horizon_days: int) -> str:
    lines = []
    lines.append("# 360 天菜單（前 30 天預覽）")
    lines.append("")
    lines.append(f"- 產生天數：{horizon_days}")
    lines.append(f"- 預覽列數：{min(30, len(days))}")
    lines.append("")
    lines.append("| Day | Date | 主菜 | 三配菜 | 湯 | 水果 | 日成本 |")
    lines.append("|---:|---|---|---|---|---|---:|")

    for day in days[:30]:
        main, sides, soup, fruit = format_items(day)
        day_idx = day.get("day_index", 0) + 1
        date = day.get("date") or "-"
        cost = float(day.get("day_cost") or 0.0)
        lines.append(
            f"| {day_idx} | {date} | {main} | {sides} | {soup} | {fruit} | {cost:.2f} |"
        )

    lines.append("")
    lines.append(f"完整 Excel（請先執行 `python scripts/generate_360_day_plan.py` 產生）：`{OUT_XLSX.relative_to(ROOT)}`")
    return "\n".join(lines)


def main() -> None:
    cfg = load_defaults()
    cfg["horizon_days"] = 360
    cfg["hard"] = cfg.get("hard") or {}
    cfg["hard"]["cost_range_per_person_per_day"] = {"min": 0, "max": 5000}

    result = plan_month(str(DB_PATH), cfg)

    if not result.get("ok", False):
        raise RuntimeError(f"Plan failed: {result.get('errors')}")

    days = result.get("days") or []
    if len(days) != 360:
        raise RuntimeError(f"Expected 360 days, got {len(days)}")

    xlsx_bytes = build_plan_workbook(cfg=cfg, result=result)
    OUT_XLSX.write_bytes(xlsx_bytes)

    OUT_MD.write_text(build_preview_markdown(days, 360), encoding="utf-8")

    print(f"Generated: {OUT_XLSX}")
    print(f"Generated: {OUT_MD}")


if __name__ == "__main__":
    main()
