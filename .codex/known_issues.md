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
