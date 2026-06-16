# Known Issues

## Playwright Chromium 無法安裝

首次發現：
2026-06-08

問題：
- Playwright Python 套件已安裝
- Chromium Browser Binary 缺失
- apt Repository 下載 HTTP 403
- Playwright CDN 下載 HTTP 403

影響：
- 無法執行 Playwright UI 測試
- 無法產生瀏覽器截圖

暫時解法：
- 使用既有瀏覽器
- 執行 UI Static Tests
- 使用 curl 驗證頁面
- 提供替代驗證證據

狀態：
Open

---

## UI Static 測試失敗

首次發現：
2026-06-08

檔案：
tests/ui_static/test_index_allowed_weekdays.mjs

問題：
- 舊版 Section Title 驗證條件失效
- Help Text 驗證條件失效

影響：
- UI Static Test 無法全數通過

狀態：
Open

---

## Starlette TestClient 缺少 httpx2

首次發現：
2026-06-08

問題：
- `fastapi.testclient.TestClient` 載入時需要 `httpx2`。
- 嘗試 `pip install httpx2` 時 PyPI 連線被代理阻擋，回傳 HTTP 403。

影響：
- 無法使用 TestClient 撰寫/執行 API integration 測試。

暫時解法：
- 使用 auth store、router function 與 dependency 的直接單元測試。
- 需要 HTTP 層驗證時，啟動 `uvicorn` 後用 `curl` 驗證。

狀態：
Open

---

## Full pytest e2e 需要外部啟動服務

首次發現：
2026-06-08

問題：
- `tests/e2e/test_e2e_excel.py` 直接呼叫 `http://127.0.0.1:18000/config/default`。
- 若執行 `pytest` 前沒有先啟動 API server，會因 `Connection refused` 失敗。

影響：
- 直接執行完整 `pytest` 會出現 119 passed、1 failed。

暫時解法：
- 先啟動 `uvicorn src.menu_planner.api.main:app --host 127.0.0.1 --port 18000` 再跑 e2e。
- 或針對本次修改執行相關 unit/UI static 測試。

狀態：
Open

---

## Vercel Serverless 本機檔案系統不適合保存帳號資料

首次發現：
2026-06-08

問題：
- Vercel Serverless 部署環境可能無法寫入專案根目錄。
- 預設 `.auth_users.json` 若在 import-time 被建立，可能造成 Function Invocation Failed。
- 已加入預設 fallback 到暫存目錄以避免啟動崩潰，但暫存目錄不保證跨冷啟動、部署或多實例保存。

影響：
- 帳號註冊、審核與登入資料在 Vercel 上若只使用 fallback 暫存 store，可能遺失或不同實例不同步。

暫時解法：
- 設定可寫且可保存的 `AUTH_USERS_FILE`（若平台支援）。
- 或設定 `AUTH_BOOTSTRAP_SUPERUSER_USERNAME` / `AUTH_BOOTSTRAP_SUPERUSER_PASSWORD` 供每次啟動建立 superuser。
- 長期應改用資料庫或集中式 auth provider。

狀態：
Open

---

## Playwright Chromium 安裝仍受 Proxy/CDN HTTP 403 限制

最後確認：
2026-06-08

問題：
- `python -m playwright install --with-deps chromium` 嘗試安裝系統依賴時，Ubuntu apt repository 經 proxy 回傳 HTTP 403。
- `python -m playwright install chromium` 下載 Chromium zip 時，`https://cdn.playwright.dev/...` 回傳 HTTP 403。

影響：
- 前端 hover tooltip 的真實瀏覽器截圖與互動驗證無法在目前環境完成。

替代驗證：
- 使用既有 Node UI static 測試檢查帳號頁、tooltip markup、導覽列與角色狀態文案。
- 啟動 FastAPI 後使用 HTTP 讀取頁面，確認 `/account.html`、`/admin`、`/` 可提供新 UI 內容。

狀態：
Open

---

## Playwright Chromium CDN HTTP 403 再次確認

最後確認：
2026-06-08

問題：
- `python -m playwright install chromium` 下載 `https://cdn.playwright.dev/.../chrome-linux64.zip` 時仍回傳 HTTP 403 Forbidden。

影響：
- 本次備份管理員角色與帳號頁權限文案為前端可見變更，但無法用 Playwright Chromium 產生實際 hover tooltip 截圖。

替代驗證：
- 使用 Node UI static 測試驗證帳號頁、角色選單、tooltip 文字與導覽列角色顯示。
- 啟動 FastAPI 並用 HTTP 檢查 `/account.html`、`/admin`、`/` 回應內容。

狀態：
Open

---

## Browser-local Auth 僅供 Vercel 唯讀測試

首次發現：
2026-06-16

問題：
- 只有在 Vercel preview/development、未設定 `AUTH_USERS_FILE` 且 `AUTH_BROWSER_LOCAL_STORE=1` 時，帳號資料才保存於瀏覽器 localStorage。
- 不同瀏覽器、不同裝置、清除站台資料後帳號不會同步或保留。
- 後端會在此模式信任瀏覽器提交的 active user/role 來簽發測試 token。

影響：
- 適合部署煙霧測試與 UI 權限流程驗證。
- 不適合正式多使用者或任何需要可信帳號控管的部署。

暫時解法：
- 正式部署設定 `AUTH_BROWSER_LOCAL_STORE=0` 並提供持久化 `AUTH_USERS_FILE` 或改用資料庫/KV/外部身份服務。

狀態：
Open
