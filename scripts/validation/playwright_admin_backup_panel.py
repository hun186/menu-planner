from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

CANDIDATE_URLS = [
    "http://host.docker.internal:18000/admin",
    "http://127.0.0.1:18000/admin",
    "http://localhost:18000/admin",
]


def probe_reachable_url(page) -> str:
    for url in CANDIDATE_URLS:
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status = resp.status if resp else None
            if status and 200 <= status < 400 and page.locator("#db_backup_select").count() > 0:
                return url
        except Exception:
            continue
    raise RuntimeError(f"No reachable admin endpoint. Tried: {CANDIDATE_URLS}")


def run_capture() -> None:
    artifacts = Path("artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        base_url = probe_reachable_url(page)
        page.wait_for_selector(".admin-top-grid", timeout=20000)

        # 嘗試聚焦在備份卡片，讓版面調整更清楚可見。
        page.locator("#db_backup_select").scroll_into_view_if_needed()
        reason_text = page.locator("#backup_reason_text").inner_text().strip()

        image_path = artifacts / "admin-backup-panel.png"
        page.screenshot(path=str(image_path), full_page=True)
        browser.close()

        print({"url": base_url, "backup_reason_text": reason_text, "screenshot": str(image_path)})


if __name__ == "__main__":
    run_capture()
