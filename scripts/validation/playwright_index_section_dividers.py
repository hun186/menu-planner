from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ARTIFACT_DIR = Path("artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)
SCREENSHOT_PATH = ARTIFACT_DIR / "index_section_dividers.png"

SECTION_TITLES = [
    "每日各角色數量",
    "每日配菜＋湯品含肉數量上限",
    "每日備菜時間上限",
    "重複限制（可互動調整）",
]


def main() -> None:
    with sync_playwright() as p:
        executable_path = Path(p.chromium.executable_path)
        if executable_path.exists():
            browser = p.chromium.launch(
                headless=True,
                executable_path=str(executable_path),
                args=["--headless=new"],
            )
        else:
            browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1200})
        page.goto("http://127.0.0.1:18000/", wait_until="networkidle")

        for title in SECTION_TITLES:
            heading = page.get_by_role("heading", name=title)
            expect(heading).to_be_visible()
            has_green_divider = heading.evaluate(
                """
                (node) => {
                    const divider = node.previousElementSibling;
                    if (!divider || divider.tagName !== 'HR' || !divider.classList.contains('hr')) {
                        return false;
                    }
                    const style = window.getComputedStyle(divider);
                    return style.borderTopWidth === '4px' && style.borderTopColor === 'rgb(36, 161, 72)';
                }
                """
            )
            if not has_green_divider:
                raise AssertionError(f"missing green divider before section: {title}")

        page.get_by_role("heading", name="每日各角色數量").scroll_into_view_if_needed()
        page.locator(".planner-settings-card").screenshot(path=str(SCREENSHOT_PATH))
        browser.close()

    print(f"section_dividers_screenshot={SCREENSHOT_PATH}")


if __name__ == "__main__":
    main()
