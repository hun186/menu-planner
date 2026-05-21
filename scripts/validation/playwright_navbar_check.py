from playwright.sync_api import sync_playwright

CANDIDATE_URLS = [
    "http://host.docker.internal:18000",
    "http://127.0.0.1:18000",
    "http://localhost:18000",
]


def probe(page):
    for url in CANDIDATE_URLS:
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=10000)
            if resp and 200 <= resp.status < 400 and page.locator('.top-nav').count() > 0:
                return url
        except Exception:
            pass
    raise RuntimeError('No UI endpoint reachable')


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1366, "height": 900})
    base = probe(page)

    nav = page.locator('.top-nav')
    nav_box_before = nav.bounding_box()
    page.mouse.wheel(0, 1600)
    page.wait_for_timeout(300)
    nav_box_after = nav.bounding_box()

    desktop_visible = page.locator('.nav-links a').count()
    page.screenshot(path='artifacts/navbar-desktop.png', full_page=True)

    mobile = browser.new_page(viewport={"width": 390, "height": 844})
    mobile.goto(base, wait_until='domcontentloaded')
    mobile.click('.nav-toggle')
    mobile.wait_for_selector('.nav-links.open')
    mobile.screenshot(path='artifacts/navbar-mobile-open.png', full_page=True)

    print({
        'base': base,
        'fixed_top_before_y': nav_box_before['y'] if nav_box_before else None,
        'fixed_top_after_y': nav_box_after['y'] if nav_box_after else None,
        'desktop_links': desktop_visible,
        'mobile_menu_open': mobile.locator('.nav-links.open').count() > 0,
    })

    mobile.close()
    browser.close()
