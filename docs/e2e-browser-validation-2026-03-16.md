# E2E Browser Validation Report (2026-03-16)

## Goal
Validate the real UI flow in one environment:
1. open homepage
2. generate 270-day menu
3. click export excel
4. confirm file downloaded and openable

## Final setup that worked
- FastAPI was started on **port 18000**:
  - `uvicorn src.menu_planner.api.main:app --host 0.0.0.0 --port 18000`
- MCP browser used matching forward config:
  - `ports_to_forward=[18000]`
- This combination successfully connected browser container to runtime app.

## What was executed

### 1) Start FastAPI server
- Command: `uvicorn src.menu_planner.api.main:app --host 0.0.0.0 --port 18000`
- Startup succeeded and server listened on `http://0.0.0.0:18000`.

### 2) Confirm homepage route is not 404 (inside runtime)
- Command: `curl -i http://127.0.0.1:18000/ | head -n 12`
- Result: `HTTP/1.1 200 OK`, returning `index.html` content.

### 3) Open website in browser container
Used MCP browser Playwright with `ports_to_forward=[18000]`, then navigated to:
- `http://localhost:18000/`
- `http://127.0.0.1:18000/`
- `http://0.0.0.0:18000/`

Observed:
- All three returned `200`
- App DOM exists (`#horizon_days` found)

### 4) Generate 270-day menu in real browser
- Action in browser: fill `#horizon_days` with `270`, click `#btn_plan`
- Result: UI message `完成。`
- Result panel content length: `1703`

### 5) Click export Excel in real browser
- Action in browser: click `#btn_export_excel` and wait for download
- Downloaded file name example: `menu_plan_20260316_103328.xlsx`
- Saved by browser script as: `artifacts/menu_plan_270_browser_18000.xlsx`

### 6) Validate downloaded file is openable
Validated in browser script using Python `zipfile` (xlsx is zip container):
- `ZIP_OK = True`
- `xl/workbook.xml` exists
- `xl/worksheets/sheet1.xml` exists

Conclusion: browser download succeeded and file structure is valid/openable.

## Earlier failure diagnosis (for context)
Earlier attempts on port 8000 in this environment showed browser-container reachability issues. Re-running with port `18000` and aligned forwarding resolved the path.

## Artifacts
- Browser success screenshot: `browser-18000-success.png`
- Browser-downloaded workbook artifact: `menu_plan_270_browser_18000.xlsx`
