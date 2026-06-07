from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

CANDIDATE_URLS = [
    "http://host.docker.internal:18000",
    "http://127.0.0.1:18000",
    "http://localhost:18000",
]
EXPECTED_ROWS = [
    ("max_same_main_in_30_days", "主菜 30 天重複上限"),
    ("max_same_noodle_in_7_days", "麵食 7 天重複上限"),
    ("max_same_noodle_in_30_days", "麵食 30 天重複上限"),
    ("max_same_side_in_7_days", "配菜 7 天重複上限"),
    ("max_same_veg_in_7_days", "純蔬 7 天重複上限"),
    ("max_same_soup_in_7_days", "湯 7 天重複上限"),
    ("max_same_fruit_in_7_days", "水果 7 天重複上限"),
]


def probe_reachable_url(page) -> str:
    for url in CANDIDATE_URLS:
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=15000)
            status = resp.status if resp else None
            if status and 200 <= status < 400 and page.locator("#repeat_limits_table").count() > 0:
                return url
        except Exception:
            continue
    raise RuntimeError(f"No reachable UI endpoint. Tried: {CANDIDATE_URLS}")


def run_check() -> None:
    Path("artifacts").mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1100})
        base_url = probe_reachable_url(page)
        print(f"Using URL: {base_url}")

        rows = []
        for key, expected_label in EXPECTED_ROWS:
            input_locator = page.locator(f'#repeat_limits_table input.repeat-limit[data-key="{key}"]')
            if input_locator.count() != 1:
                raise AssertionError(f"Expected exactly one repeat limit input for {key}")
            row = input_locator.locator("xpath=ancestor::tr[1]")
            row_text = row.inner_text()
            if expected_label not in row_text:
                raise AssertionError(f"Missing label {expected_label!r} in row text {row_text!r}")
            rows.append(row_text.replace("\t", " "))

        page.locator("#repeat_limits_table").screenshot(path="artifacts/repeat-limits-table.png")
        browser.close()
        print({"repeat_limit_rows": rows})


if __name__ == "__main__":
    run_check()
