from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ARTIFACT_DIR = Path("artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)
MEAT_SCREENSHOT_PATH = ARTIFACT_DIR / "meat_limit_weekday_columns.png"
MEAT_MOBILE_SCREENSHOT_PATH = ARTIFACT_DIR / "meat_limit_weekday_columns_mobile.png"


def main() -> None:
    with sync_playwright() as p:
        executable_path = Path(p.chromium.executable_path)
        if executable_path.exists():
            browser = p.chromium.launch(headless=True, executable_path=str(executable_path), args=["--headless=new"])
        else:
            browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.goto("http://127.0.0.1:18000/", wait_until="networkidle")

        table = page.locator("#weekday_meat_limits_table")
        expect(table).to_be_visible()
        expect(table.locator("thead")).to_contain_text("星期一星期二星期三星期四星期五星期六星期日")
        expect(table.locator("input.weekday-meat-limit")).to_have_count(7)
        expect(page.locator("#weekday_meat_add_select")).to_have_count(0)
        expect(page.locator(".weekday-meat-delete")).to_have_count(0)

        monday = table.locator('input[data-weekday="1"]')
        wednesday = table.locator('input[data-weekday="3"]')
        monday.fill("1")
        wednesday.fill("3")

        cfg_json = page.locator("#cfg_json")
        expect(cfg_json).to_contain_text('"per_weekday_side_soup_meat_limit"')
        expect(cfg_json).to_contain_text('"1": 1')
        expect(cfg_json).to_contain_text('"3": 3')

        table.screenshot(path=str(MEAT_SCREENSHOT_PATH))

        page.set_viewport_size({"width": 390, "height": 900})
        table.scroll_into_view_if_needed()
        settings_card = page.locator(".planner-settings-card")
        card_box = settings_card.bounding_box()
        table_box = table.bounding_box()
        input_box = wednesday.bounding_box()
        if not input_box or input_box["width"] < 40:
            raise AssertionError(f"meat weekday input too narrow on mobile: {input_box}")
        if not card_box or not table_box:
            raise AssertionError(f"missing mobile layout boxes: card={card_box}, table={table_box}")
        if table_box["x"] + table_box["width"] > card_box["x"] + card_box["width"] + 1:
            raise AssertionError(f"meat table escapes settings card on mobile: card={card_box}, table={table_box}")
        settings_card.screenshot(path=str(MEAT_MOBILE_SCREENSHOT_PATH))
        browser.close()

    print(f"meat_screenshot={MEAT_SCREENSHOT_PATH}")
    print(f"meat_mobile_screenshot={MEAT_MOBILE_SCREENSHOT_PATH}")


if __name__ == "__main__":
    main()
