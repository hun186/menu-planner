from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ARTIFACT_DIR = Path("artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)
SCREENSHOT_PATH = ARTIFACT_DIR / "editable_empty_role_selectors_mobile.png"


def main() -> None:
    with sync_playwright() as p:
        executable_path = Path(p.chromium.executable_path)
        if executable_path.exists():
            browser = p.chromium.launch(headless=True, executable_path=str(executable_path), args=["--headless=new"])
        else:
            browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 390, "height": 900})
        page.goto("http://127.0.0.1:18000/", wait_until="networkidle")
        page.evaluate(
            """
            async () => {
              const { renderResult } = await import('/render.js');
              window.$ = (selector) => {
                if (selector !== '#result') throw new Error(`Unexpected selector: ${selector}`);
                return {
                  html(value) {
                    document.querySelector('#result').innerHTML = String(value || '');
                  },
                };
              };
              const result = {
                summary: { days: 1, total_cost: 0, avg_cost_per_day: 0, total_score: 0 },
                days: [{
                  day_index: 0,
                  date: '2026-03-18',
                  is_scheduled: true,
                  items: {
                    main: { id: 'm1', name: '主菜A' },
                    sides: [],
                    veg: { id: '', name: '' },
                    soup: { id: '', name: '' },
                    fruit: { id: '', name: '' },
                  },
                  day_cost: 0,
                  score: 0,
                  score_breakdown: {},
                }],
                errors: [],
              };
              const cfg = {
                people: 250,
                per_day_roles: { main: 1, noodle: 1, side: 5, veg: 5, soup: 1, fruit: 1 },
                per_weekday_roles: {
                  3: { main: 1, noodle: 1, side: 5, veg: 5, soup: 1, fruit: 1 },
                },
              };
              renderResult(result, cfg, { editable: true });
            }
            """
        )

        for text in ["（選擇麵食1）", "（選擇配菜1）", "（選擇配菜2）", "（選擇配菜3）", "（選擇配菜4）", "（選擇配菜5）", "（選擇純蔬1）", "（選擇純蔬2）", "（選擇純蔬3）", "（選擇純蔬4）", "（選擇純蔬5）", "（選擇湯品1）", "（選擇水果1）"]:
            expect(page.get_by_role("button", name=text)).to_be_visible()

        page.locator("#result").screenshot(path=str(SCREENSHOT_PATH))
        browser.close()

    print(f"editable_empty_selectors_screenshot={SCREENSHOT_PATH}")


if __name__ == "__main__":
    main()
