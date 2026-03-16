# UI 生成菜單檢查紀錄

## 目的
確認 API 網頁介面可成功執行「產生菜單」核心流程，且無後端錯誤。

## 檢查結果
- `/` 首頁可正常回應（HTTP 200）。
- `POST /plan` 以預設設定、`horizon_days=30` 執行成功：
  - `ok=True`
  - 回傳 `days=30`
  - `errors=0`

## 瀏覽器自動點擊狀態
- 已嘗試使用 Codex browser/playwright 模擬點擊「產生菜單」。
- 本環境 browser 工具有不穩定現象（一次 timeout、一次 chromium SIGSEGV），因此改以 API 端到端驗證確認生成功能無 bug。

## 可重跑指令
1. 啟動服務
   - `python -m uvicorn src.menu_planner.api.main:app --host 0.0.0.0 --port 18000`
2. 送出 30 天排程請求
   - 以 `python` + `urllib.request` 呼叫：先抓 `/config/default`，再 POST `/plan`。


## Playwright 自動探測版（新增）
- 新增 `scripts/playwright_ui_smoke.py`：會依序嘗試
  1. `http://host.docker.internal:18000`
  2. `http://127.0.0.1:18000`
  3. `http://localhost:18000`
- 探測到可用 UI 後，才會點擊「產生菜單」按鈕並等待結果。
