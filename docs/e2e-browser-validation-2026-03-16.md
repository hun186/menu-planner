# E2E Browser Validation Report (2026-03-16)

## Goal
Validate the real UI flow in one environment:
1. open homepage
2. generate 270-day menu
3. click export excel
4. confirm file downloaded and openable

## What was executed

### 1) Start FastAPI server
- Command: `uvicorn src.menu_planner.api.main:app --host 0.0.0.0 --port 8000`
- Startup succeeded and server listened on `http://0.0.0.0:8000`.

### 2) Confirm homepage route is not 404 (inside runtime)
- Command: `curl -i http://127.0.0.1:8000/ | head -n 15`
- Result: `HTTP/1.1 200 OK`, returning `index.html` content.

### 3) Browser-container validation with forwarded port (real browser path)
Used MCP browser Playwright with `ports_to_forward=[8000]` and retried all local variants:
- `http://localhost:8000/`
- `http://127.0.0.1:8000/`
- `http://0.0.0.0:8000/`

Observed from browser container:
- All three returned `404` and none contained app DOM (`#horizon_days` not found).
- No corresponding browser GETs were logged by this runtime's uvicorn process.

Conclusion:
- This is **not** homepage route/static file logic in the FastAPI runtime (runtime itself serves `/` as 200).
- This is a **sandbox/browser-network forwarding isolation** issue between browser container and this runtime.

### 4) Fallback verification in same runtime (download artifact + openability)
Because browser container could not reach the app, executed end-to-end fallback in the same runtime using stdlib HTTP + `openpyxl`:
- `GET /config/default`
- set `horizon_days=270`
- `POST /plan`
- `POST /export/excel`
- write file to `artifacts/menu_plan_270_runtime.xlsx`
- open file via `openpyxl.load_workbook`

Observed:
- `GET /config/default` => `200`
- `POST /plan` => `200`, `ok=true`
- `POST /export/excel` => `200`
- workbook open succeeded
- sheets: `['菜單', '摘要', '設定']`
- first sheet `A1` = `日期`

## Artifacts
- Browser failure screenshot (MCP artifact): `browser-failed-home.png`
- Runtime generated workbook (not committed): `artifacts/menu_plan_270_runtime.xlsx`
