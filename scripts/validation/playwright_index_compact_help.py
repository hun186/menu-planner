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

        page.get_by_label("查看禁用菜色說明").click()
        exclude_help = page.locator(".compact-help-panel", has_text="可先用角色縮小範圍")
        exclude_help.wait_for(state="visible", timeout=5000)
        exclude_text = exclude_help.inner_text()
        print({"exclude_help": exclude_text})
        page.screenshot(path=str(ARTIFACT_DIR / "index-exclude-dish-help.png"), full_page=True)

        page.get_by_label("查看禁用菜色說明").click()
        page.get_by_label("查看允許週幾說明").click()
        allowed_help = page.locator(".compact-help-panel", has_text="管理者在資料庫管理設定")
        allowed_help.wait_for(state="visible", timeout=5000)
        allowed_text = allowed_help.inner_text()
        print({"allowed_weekdays_help": allowed_text})
        page.screenshot(path=str(ARTIFACT_DIR / "index-allowed-weekdays-help.png"), full_page=True)

        browser.close()


if __name__ == "__main__":
    run_check()
