from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

CANDIDATE_URLS = [
    "http://host.docker.internal:18000",
    "http://127.0.0.1:18000",
    "http://localhost:18000",
]


def probe_reachable_url(page) -> str:
    for base_url in CANDIDATE_URLS:
        try:
            resp = page.goto(f"{base_url}/admin", wait_until="domcontentloaded", timeout=15000)
            status = resp.status if resp else None
            if status and 200 <= status < 400 and page.locator("#dish_tbl").count() > 0:
                return base_url
        except Exception:
            continue
    raise RuntimeError(f"No reachable admin endpoint. Tried: {[url + '/admin' for url in CANDIDATE_URLS]}")


def run_capture() -> None:
    artifacts = Path("artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        base_url = probe_reachable_url(page)

        expect(page.locator("#conv_factor")).to_have_attribute("step", "0.01")
        expect(page.locator("#dish_tbl thead")).to_contain_text("允許供應日")
        page.locator("#conv_panel").evaluate("el => el.open = true")
        page.wait_for_timeout(500)

        first_factor = page.locator("#conv_tbl tbody tr td:nth-child(3)").first()
        expect(first_factor).to_be_visible(timeout=20000)
        factor_text = first_factor.inner_text().strip()
        if not re.fullmatch(r"\d+(?:\.\d{2})", factor_text):
            raise AssertionError(f"Expected factor to display with exactly two decimals, got: {factor_text!r}")

        cost_header = page.locator("#dish_tbl th:nth-child(7)").bounding_box()
        action_header = page.locator("#dish_tbl th:nth-child(8)").bounding_box()
        if not cost_header or not action_header:
            raise AssertionError("Could not measure dish table cost/action columns")
        if cost_header["width"] < action_header["width"] - 2:
            raise AssertionError(
                f"Expected cost column to be at least as wide as action column; "
                f"cost={cost_header['width']}, action={action_header['width']}"
            )

        page.screenshot(path=str(artifacts / "admin-display-tuning.png"), full_page=True)

        page.goto(base_url, wait_until="domcontentloaded", timeout=15000)
        expect(page.locator("h3", has_text="菜色供應日設定（排菜設定）")).to_be_visible()
        expect(page.locator("#allowed_dish_weekday_picker")).to_contain_text("星期一")
        expect(page.locator("#allowed_dish_weekday_picker")).to_contain_text("星期日")
        page.screenshot(path=str(artifacts / "index-supply-day-wording.png"), full_page=True)

        browser.close()
        print(
            {
                "url": base_url,
                "factor_text_sample": factor_text,
                "cost_column_width": cost_header["width"],
                "action_column_width": action_header["width"],
                "screenshots": [
                    str(artifacts / "admin-display-tuning.png"),
                    str(artifacts / "index-supply-day-wording.png"),
                ],
            }
        )


if __name__ == "__main__":
    run_capture()
