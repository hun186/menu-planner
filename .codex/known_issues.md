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