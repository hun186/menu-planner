# E2E Browser Validation Report (2026-03-16)

## Goal
Validate the real UI flow in one environment:
1. open homepage
2. generate 270-day menu
3. click export excel
4. confirm file downloaded and openable

## What was executed

### Server start
- `uvicorn src.menu_planner.api.main:app --host 0.0.0.0 --port 8000`

### Homepage route sanity check
- `curl -i http://127.0.0.1:8000/ | head -n 20`
- Result: `HTTP/1.1 200 OK` and HTML content returned.

### Browser-container attempt (required real browser path)
Used MCP browser Playwright with forwarded port 8000.
- Attempted navigation to:
  - `http://localhost:8000/`
  - `http://127.0.0.1:8000/`
  - `http://0.0.0.0:8000/`
- Observed from browser container:
  - `404 Not Found` page (non-app HTML)
  - navigation interruption to `chrome-error://chromewebdata/`
  - `host.docker.internal` DNS unresolved

Conclusion: browser container could not reach this runtime's FastAPI server even after `ports_to_forward`, which indicates sandbox/network forwarding isolation issue rather than app route/static issue.

### Fallback verification (same runtime, API + workbook openability)
Executed Python validation using stdlib urllib + openpyxl:
- load defaults (`/config/default`)
- set `horizon_days=270`
- run plan (`/plan`)
- export (`/export/excel`)
- save as `artifacts/menu_plan_270.xlsx`
- open workbook via `openpyxl.load_workbook`

Observed:
- plan status `200`, `ok=true`
- export status `200`
- workbook opened successfully
- sheets: `['菜單', '摘要', '設定']`
- first sheet cell `A1` = `日期`

## Artifact
- `artifacts/menu_plan_270.xlsx` (generated in runtime, not committed)
