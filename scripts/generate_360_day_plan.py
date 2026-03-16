from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.menu_planner.api.export_excel import build_plan_workbook
from src.menu_planner.config.loader import load_defaults
from src.menu_planner.engine.planner import plan_month

DB_PATH = ROOT / "data" / "menu.db"
OUT_XLSX = ROOT / "data" / "menu_plan_360d.xlsx"
DEFAULT_OUT_MD = ROOT / "docs" / "menu_plan_360_preview.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate 360-day menu plan and markdown preview")
    parser.add_argument("--preview-days", type=int, default=30, help="How many days to show in markdown preview")
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUT_MD, help="Output markdown preview path")
    return parser.parse_args()


def format_items(day: dict) -> tuple[str, str, str, str]:
    items = day.get("items") or {}
    main = (items.get("main") or {}).get("name") or "-"
    sides = items.get("sides") or []
    side_names = "、".join([s.get("name") or "-" for s in sides]) if sides else "-"
    soup = (items.get("soup") or {}).get("name") or "-"
    fruit = (items.get("fruit") or {}).get("name") or "-"
    return main, side_names, soup, fruit


def build_preview_markdown(days: list[dict], horizon_days: int, preview_days: int) -> str:
    lines = []
    lines.append(f"# 360 天菜單（前 {preview_days} 天預覽）")
    lines.append("")
    lines.append(f"- 產生天數：{horizon_days}")
    lines.append(f"- 預覽列數：{min(preview_days, len(days))}")
    lines.append("")
    lines.append("| Day | Date | 主菜 | 三配菜 | 湯 | 水果 | 日成本 |")
    lines.append("|---:|---|---|---|---|---|---:|")

    for day in days[:preview_days]:
        main, sides, soup, fruit = format_items(day)
        day_idx = day.get("day_index", 0) + 1
        date = day.get("date") or "-"
        cost = float(day.get("day_cost") or 0.0)
        lines.append(
            f"| {day_idx} | {date} | {main} | {sides} | {soup} | {fruit} | {cost:.2f} |"
        )

    lines.append("")
    lines.append(
        "完整 Excel（請先執行 `python scripts/generate_360_day_plan.py` 產生）："
        f"`{OUT_XLSX.relative_to(ROOT)}`"
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    preview_days = max(1, args.preview_days)
    out_md = args.out_md if args.out_md.is_absolute() else (ROOT / args.out_md)

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

    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(build_preview_markdown(days, 360, preview_days), encoding="utf-8")

    print(f"Generated: {OUT_XLSX}")
    print(f"Generated: {out_md}")


if __name__ == "__main__":
    main()
