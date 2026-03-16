from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

CANDIDATE_URLS = [
    "http://host.docker.internal:18000",
    "http://127.0.0.1:18000",
    "http://localhost:18000",
]


def probe_reachable_url(page) -> str:
    for url in CANDIDATE_URLS:
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status = resp.status if resp else None
            if status and 200 <= status < 400:
                if page.locator("#horizon_days").count() > 0:
                    return url
        except Exception:
            continue
    raise RuntimeError(f"No reachable UI endpoint. Tried: {CANDIDATE_URLS}")


def run_smoke() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        base_url = probe_reachable_url(page)
        print(f"Using URL: {base_url}")

        page.fill("#horizon_days", "30")
        page.click("#btn_plan")

        try:
            page.wait_for_selector("#result table, #result .errbox", timeout=120000)
        except PlaywrightTimeoutError as e:
            page.screenshot(path="artifacts/ui-plan-timeout.png", full_page=True)
            raise RuntimeError("Plan button test timed out") from e

        msg = page.inner_text("#msg")
        table_count = page.locator("#result table").count()
        errbox_count = page.locator("#result .errbox").count()

        page.screenshot(path="artifacts/ui-plan-success.png", full_page=True)
        browser.close()

        print({
            "msg": msg,
            "table_count": table_count,
            "errbox_count": errbox_count,
        })


if __name__ == "__main__":
    run_smoke()
