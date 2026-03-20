from __future__ import annotations

from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

CANDIDATE_BASE_URLS = [
    "http://127.0.0.1:18000",
    "http://localhost:18000",
    "http://host.docker.internal:18000",
]

ING_ID = "e2e_cost_warn_ing"
DISH_ID = "e2e_cost_warn_dish"
ARTIFACT_PATH = Path("artifacts/admin-cost-tooltip.png")


def resolve_base_url() -> str:
    for base in CANDIDATE_BASE_URLS:
        try:
            resp = requests.get(f"{base}/admin.html", timeout=5)
            if resp.status_code == 200:
                return base
        except Exception:
            continue
    raise RuntimeError(f"No reachable admin UI endpoint. Tried: {CANDIDATE_BASE_URLS}")


def upsert_warning_fixture(base_url: str) -> None:
    ing_payload = {
        "name": "E2E成本警示食材",
        "category": "vegetable",
        "protein_group": None,
        "default_unit": "g",
    }
    dish_payload = {
        "name": "E2E成本警示菜色",
        "role": "side",
        "meat_type": None,
        "cuisine": "test",
        "tags": ["e2e", "cost-warning"],
    }
    links_payload = [{"ingredient_id": ING_ID, "qty": 100, "unit": "g"}]

    for method, path, body in [
        ("PUT", f"/admin/catalog/ingredients/{ING_ID}", ing_payload),
        ("PUT", f"/admin/catalog/dishes/{DISH_ID}", dish_payload),
        ("PUT", f"/admin/catalog/dishes/{DISH_ID}/ingredients", links_payload),
    ]:
        resp = requests.request(method, f"{base_url}{path}", json=body, timeout=10)
        if resp.status_code >= 400:
            raise RuntimeError(f"Fixture setup failed: {method} {path} => {resp.status_code} {resp.text}")


def run() -> None:
    base_url = resolve_base_url()
    upsert_warning_fixture(base_url)
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(f"{base_url}/admin.html", wait_until="domcontentloaded", timeout=30000)

        page.fill("#dish_q", DISH_ID)
        page.wait_for_timeout(800)

        warning_icon = page.locator("#dish_tbl tbody tr .cost-warning-icon").first
        warning_icon.wait_for(state="visible", timeout=20000)
        warning_icon.hover()
        page.wait_for_timeout(300)

        tooltip_text = warning_icon.get_attribute("data-tooltip") or ""
        if "成本計算異常" not in tooltip_text:
            raise RuntimeError(f"Unexpected tooltip text: {tooltip_text}")

        page.screenshot(path=str(ARTIFACT_PATH), full_page=True)
        browser.close()

    print({
        "base_url": base_url,
        "dish_id": DISH_ID,
        "artifact": str(ARTIFACT_PATH),
        "tooltip_prefix": tooltip_text.split("\n", 1)[0],
    })


if __name__ == "__main__":
    run()
