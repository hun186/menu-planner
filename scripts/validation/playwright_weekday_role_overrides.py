from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ARTIFACT_DIR = Path("artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)
WEEKDAY_SCREENSHOT_PATH = ARTIFACT_DIR / "weekday_role_overrides.png"
DAILY_SCREENSHOT_PATH = ARTIFACT_DIR / "daily_role_counts_compact.png"
WEEKDAY_MOBILE_SCREENSHOT_PATH = ARTIFACT_DIR / "weekday_role_overrides_mobile.png"


def main() -> None:
    with sync_playwright() as p:
        executable_path = Path(p.chromium.executable_path)
        if executable_path.exists():
            browser = p.chromium.launch(headless=True, executable_path=str(executable_path), args=["--headless=new"])
        else:
            browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto("http://127.0.0.1:18000/", wait_until="networkidle")

        daily_table = page.locator("#daily_role_counts_table")
        expect(daily_table).to_be_visible()
        expect(daily_table.locator("thead")).to_contain_text("設定主菜麵食配菜純蔬湯水果")
        daily_row = daily_table.locator("tbody tr")
        expect(daily_row).to_have_count(1)
        expect(daily_row).to_contain_text("全域每日預設")
        expect(daily_row.locator("input.daily-role-count")).to_have_count(6)
        daily_row.locator('input[data-role="noodle"]').fill("1")

        cfg_json = page.locator("#cfg_json")
        expect(cfg_json).to_contain_text('"per_day_roles"')
        expect(cfg_json).to_contain_text('"noodle": 1')

        daily_table.screenshot(path=str(DAILY_SCREENSHOT_PATH))

        add_select = page.locator("#weekday_role_add_select")
        add_button = page.locator("#weekday_role_add")
        expect(add_button).to_be_visible()

        add_select.select_option("1")
        add_button.click()

        monday_row = page.locator('#weekday_role_counts_table tr[data-weekday="1"]')
        expect(monday_row).to_be_visible()
        monday_row.locator('input[data-role="noodle"]').fill("2")
        monday_row.locator('input[data-role="side"]').fill("3")

        expect(cfg_json).to_contain_text('"1": {')
        expect(cfg_json).to_contain_text('"noodle": 2')
        expect(cfg_json).to_contain_text('"side": 3')

        wednesday_row = page.locator('#weekday_role_counts_table tr[data-weekday="3"]')
        expect(wednesday_row).to_be_visible()
        wednesday_row.locator(".weekday-role-delete").click()
        expect(wednesday_row).to_have_count(0)
        expect(add_select.locator('option[value="3"]')).to_be_enabled()

        page.locator("#weekday_role_counts_table").screenshot(path=str(WEEKDAY_SCREENSHOT_PATH))

        page.set_viewport_size({"width": 390, "height": 900})
        page.locator("#weekday_role_counts_table").scroll_into_view_if_needed()
        monday_side = monday_row.locator('input[data-role="side"]')
        expect(monday_side).to_have_value("3")
        box = monday_side.bounding_box()
        if not box or box["width"] < 40:
            raise AssertionError(f"weekday side input too narrow on mobile: {box}")
        page.locator("#weekday_role_counts_table").screenshot(path=str(WEEKDAY_MOBILE_SCREENSHOT_PATH))
        browser.close()

    print(f"daily_screenshot={DAILY_SCREENSHOT_PATH}")
    print(f"weekday_screenshot={WEEKDAY_SCREENSHOT_PATH}")
    print(f"weekday_mobile_screenshot={WEEKDAY_MOBILE_SCREENSHOT_PATH}")


if __name__ == "__main__":
    main()
