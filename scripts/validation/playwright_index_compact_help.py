from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

CANDIDATE_URLS = [
    "http://host.docker.internal:18000",
    "http://127.0.0.1:18000",
    "http://localhost:18000",
]
ARTIFACT_DIR = Path("artifacts")


def probe_reachable_url(page) -> str:
    for url in CANDIDATE_URLS:
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status = resp.status if resp else None
            if status and 200 <= status < 400 and page.locator("#dish_search").count() > 0:
                return url
        except Exception:
            continue
    raise RuntimeError(f"No reachable UI endpoint. Tried: {CANDIDATE_URLS}")


def run_check() -> None:
    ARTIFACT_DIR.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        base_url = probe_reachable_url(page)
        print(f"Using URL: {base_url}")

        help_checks = [
            (
                "查看每日各角色數量說明",
                "數量為 0 代表該日不排該角色",
                "daily_role_counts_help",
                "index-daily-role-counts-help.png",
            ),
            (
                "查看每日配菜與湯品含肉數量上限說明",
                "計算配菜與湯品中，菜色肉類為雞",
                "side_soup_meat_limit_help",
                "index-side-soup-meat-limit-help.png",
            ),
            (
                "查看每日備菜時間上限說明",
                "全日已排菜色的「備菜時間（分鐘）」總和不可超過此上限",
                "prep_time_limit_help",
                "index-prep-time-limit-help.png",
            ),
            (
                "查看禁用菜色說明",
                "可先用角色縮小範圍",
                "exclude_help",
                "index-exclude-dish-help.png",
            ),
        ]
        for label, text, print_key, screenshot_name in help_checks:
            page.get_by_label(label).click()
            help_panel = page.locator(".compact-help-panel", has_text=text)
            help_panel.wait_for(state="visible", timeout=5000)
            help_text = help_panel.inner_text()
            print({print_key: help_text})
            page.screenshot(path=str(ARTIFACT_DIR / screenshot_name), full_page=True)
            page.get_by_label(label).click()

        if page.get_by_text("以兩欄並排呈現，保留完整限制名稱，同時減少垂直捲動。").count() != 0:
            raise AssertionError("Repeat-limit layout explanation should not be visible to menu-planning users")

        page.get_by_label("查看允許週幾說明").click()
        allowed_help = page.locator(".compact-help-panel", has_text="管理者在資料庫管理設定")
        allowed_help.wait_for(state="visible", timeout=5000)
        allowed_text = allowed_help.inner_text()
        print({"allowed_weekdays_help": allowed_text})
        page.screenshot(path=str(ARTIFACT_DIR / "index-allowed-weekdays-help.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    run_check()
