# Known Issues

- 2026-06-08: Playwright Python package is installed, but Chromium browser binaries are absent in this environment. `python -m playwright install --with-deps chromium` fails because apt repositories return HTTP 403 via proxy, and `python -m playwright install chromium` fails because the Playwright CDN returns HTTP 403.
- 2026-06-08: Running `node --test tests/ui_static/*.mjs` currently reports two pre-existing static expectation failures in `tests/ui_static/test_index_allowed_weekdays.mjs` related to older section-title markup/help text assumptions.
- 2026-06-08: Reconfirmed during result-column UI work that Playwright Chromium is unavailable: `python -c "import playwright"` succeeds, Chromium launch reports the missing headless-shell executable, and `python -m playwright install --with-deps chromium` fails at apt repository fetches with HTTP 403 via proxy.
