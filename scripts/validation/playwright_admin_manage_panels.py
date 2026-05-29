from __future__ import annotations

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

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
            if status and 200 <= status < 400 and page.locator("#ingredient_manage_card").count() > 0:
                return url
        except Exception:
            continue
    raise RuntimeError(f"No reachable admin endpoint. Tried: {CANDIDATE_URLS}")


def run_capture() -> None:
    artifacts = Path("artifacts")
    artifacts.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        page.add_init_script("window.localStorage.removeItem('menuPlanner.admin.managePanels')")
        base_url = probe_reachable_url(page)
        page.wait_for_selector("#dish_manage_card", timeout=20000)

        ingredient_card = page.locator("#ingredient_manage_card")
        dish_card = page.locator("#dish_manage_card")
        ingredient_body = page.locator("#ingredient_manage_body")
        dish_body = page.locator("#dish_manage_body")

        expect(ingredient_body).to_be_visible()
        expect(dish_body).to_be_visible()
        initial_dish_width = dish_card.bounding_box()["width"]
        page.screenshot(path=str(artifacts / "admin-manage-panels-expanded.png"), full_page=True)

        page.get_by_role("button", name="隱藏食材管理").click()
        expect(ingredient_body).to_be_hidden()
        expect(page.get_by_role("button", name="展開食材管理")).to_have_attribute("aria-expanded", "false")
        expanded_dish_width = dish_card.bounding_box()["width"]
        if expanded_dish_width <= initial_dish_width:
            raise AssertionError(
                f"Dish panel did not expand after hiding ingredients: {expanded_dish_width} <= {initial_dish_width}"
            )
        page.screenshot(path=str(artifacts / "admin-manage-panels-ingredient-collapsed.png"), full_page=True)

        page.get_by_role("button", name="隱藏菜色管理").click()
        expect(dish_body).to_be_hidden()
        expect(page.get_by_role("button", name="展開菜色管理")).to_have_attribute("aria-expanded", "false")
        page.screenshot(path=str(artifacts / "admin-manage-panels-both-collapsed.png"), full_page=True)

        page.reload(wait_until="domcontentloaded")
        expect(ingredient_body).to_be_hidden()
        expect(dish_body).to_be_hidden()

        page.get_by_role("button", name="展開食材管理").click()
        page.get_by_role("button", name="展開菜色管理").click()
        expect(ingredient_body).to_be_visible()
        expect(dish_body).to_be_visible()
        page.screenshot(path=str(artifacts / "admin-manage-panels-restored.png"), full_page=True)
        browser.close()

        print(
            {
                "url": base_url,
                "initial_dish_width": initial_dish_width,
                "expanded_dish_width": expanded_dish_width,
                "screenshots": [
                    str(artifacts / "admin-manage-panels-expanded.png"),
                    str(artifacts / "admin-manage-panels-ingredient-collapsed.png"),
                    str(artifacts / "admin-manage-panels-both-collapsed.png"),
                    str(artifacts / "admin-manage-panels-restored.png"),
                ],
            }
        )


if __name__ == "__main__":
    run_capture()
