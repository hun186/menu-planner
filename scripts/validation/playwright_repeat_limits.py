from __future__ import annotations

from pathlib import Path

from playwright.sync_api import sync_playwright

CANDIDATE_URLS = [
    "http://host.docker.internal:18000",
    "http://127.0.0.1:18000",
    "http://localhost:18000",
]
EXPECTED_LIMITS = [
    ("max_same_main_in_30_days", "主菜 30 天重複上限"),
    ("max_same_noodle_in_7_days", "麵食 7 天重複上限"),
    ("max_same_noodle_in_30_days", "麵食 30 天重複上限"),
    ("max_same_side_in_7_days", "配菜 7 天重複上限"),
    ("max_same_veg_in_7_days", "純蔬 7 天重複上限"),
    ("max_same_soup_in_7_days", "湯 7 天重複上限"),
    ("max_same_fruit_in_7_days", "水果 7 天重複上限"),
    ("max_same_ingredient_in_window_days", "食材窗口重複上限"),
    ("ingredient_repeat_window_days", "食材窗口天數"),
    ("max_consecutive_ingredient_days", "食材連續天數上限"),
]
EXPECTED_QUOTA_HEADERS = ["每週上限", "雞", "豬", "牛", "海鮮", "素"]


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

        quota_headers = page.locator("#weekly_quota_table thead th").all_inner_texts()
        if quota_headers != EXPECTED_QUOTA_HEADERS:
            raise AssertionError(f"Unexpected weekly quota headers: {quota_headers!r}")
        quota_body_rows = page.locator("#weekly_quota_table tbody tr").count()
        if quota_body_rows != 1:
            raise AssertionError(f"Expected weekly quota matrix to use one body row, got {quota_body_rows}")

        rows = []
        for key, expected_label in EXPECTED_LIMITS:
            input_locator = page.locator(f'#repeat_limits_table input.repeat-limit[data-key="{key}"]')
            if input_locator.count() != 1:
                raise AssertionError(f"Expected exactly one repeat limit input for {key}")
            row = input_locator.locator("xpath=ancestor::tr[1]")
            row_text = row.inner_text()
            if expected_label not in row_text:
                raise AssertionError(f"Missing label {expected_label!r} in row text {row_text!r}")
            rows.append(row_text.replace("\t", " "))

        repeat_headers = page.locator("#repeat_limits_table thead th").all_inner_texts()
        if repeat_headers != ["限制項目", "數值", "限制項目", "數值"]:
            raise AssertionError(f"Unexpected repeat limit headers: {repeat_headers!r}")

        page.locator("#weekly_quota_table").screenshot(path="artifacts/weekly-quota-table.png")
        page.locator("#repeat_limits_table").screenshot(path="artifacts/repeat-limits-table.png")
        browser.close()
        print({"weekly_quota_headers": quota_headers, "repeat_limit_rows": rows})


if __name__ == "__main__":
    run_check()
