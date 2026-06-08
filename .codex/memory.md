# Project Memory

## 2026-06-08

### 完成項目

- Excel 菜單工作表新增每日「人數」欄位。
- Excel 匯出改用內容導向欄寬自動調整機制。
- 更新菜單規劃頁面副標題說明。
- 新增結果表格欄位顯示／隱藏功能。
- 欄位顯示偏好儲存於 Local Storage。
- 完成結果表格功能驗證。

### 驗證結果

- Node UI Static 測試（相關功能）通過。
- 完整 UI Static Suite 仍有既有的 `test_index_allowed_weekdays.mjs` 驗證失敗。
- Playwright 驗證因 Chromium 無法安裝而未執行。

### 相關文件

- 詳細設計決策：`.codex/decisions.md`
- 已知問題：`.codex/known_issues.md`

## 2026-06-08 Auth System Integration

### 任務目的

- 參考 `portable_auth_pack`，在 Menu Planner 導入帳號管理能力，改善原本只支援 `MENU_ADMIN_KEY` 的管理權限模式。

### 主要修改內容

- 新增 FastAPI auth 模組，支援註冊、登入、目前使用者查詢、使用者清單、核准、拒絕與刪除帳號。
- 新增 PBKDF2 密碼雜湊、本機 JSON 使用者儲存、HMAC Bearer token 與 superuser dependency。
- 管理寫入 API 最終改為只接受 superuser Bearer token；舊版 `X-Admin-Key` 相容路徑已於後續修正移除。
- 管理頁新增帳號登入、註冊、登入狀態檢查、登出與帳號審核 UI。
- 前端 HTTP helper 新增 auth token/session 管理，管理寫入請求會自動附加 Bearer token。
- 將 `.auth_users.json` 加入 `.gitignore`，避免提交本機帳號雜湊資料。

### 驗證結果

- `python -c "import fastapi, starlette, pydantic, openpyxl, pytest"` 通過。
- `PYTHONPATH=. pytest tests/unit/test_auth_system.py tests/unit/test_admin_catalog_read_routes_auth.py` 通過。
- `node tests/ui_static/test_admin_auth_panel.mjs` 通過。
- `node tests/ui_static/test_admin_smoke.mjs` 通過。
- 使用 `uvicorn` 啟動後，以 `curl` 驗證 `/v1/auth/register`、`/v1/auth/login`、`/v1/auth/me` 與 `/admin` 帳號管理 UI 文字均可用。
- `PYTHONPATH=. pytest` 有 119 passed、1 failed；失敗為既有 e2e 測試未先啟動 `127.0.0.1:18000` 服務。
- Playwright Chromium 安裝仍受 apt/proxy HTTP 403 限制，無法產生瀏覽器截圖；已用 curl 與 UI static 測試提供替代證據。

### 重要結論

- 第一個註冊帳號會自動成為 active superuser，避免新部署沒有 bootstrap 帳號時無法進入帳號審核流程。
- 後續註冊帳號預設為 pending，需由 superuser 審核後才能登入使用。

## 2026-06-08 Remove Legacy Admin Key

### 任務目的

- 因專案尚未實際使用舊版 `X-Admin-Key` / `MENU_ADMIN_KEY` 機制，移除相容層，改為只使用帳號管理系統授權。

### 主要修改內容

- 後端管理寫入 dependency 改名為 `require_admin_user`，只接受 active superuser Bearer token。
- 移除前端 Admin Key 輸入、Local Storage 金鑰讀取與 `X-Admin-Key` header 注入。
- 管理頁錯誤提示改為提醒使用 superuser 帳號登入。
- README 改以 `AUTH_SECRET`、`AUTH_USERS_FILE` 與帳號註冊/審核流程作為管理端設定說明。
- 更新 auth 與 UI static 測試，確認不再送出 `X-Admin-Key`。

### 驗證結果

- `python -c "import fastapi, starlette, pydantic, openpyxl, pytest"` 通過。
- `PYTHONPATH=. pytest tests/unit/test_auth_system.py tests/unit/test_admin_catalog_read_routes_auth.py` 通過。
- `node tests/ui_static/test_admin_auth_panel.mjs` 通過。
- `node tests/ui_static/test_admin_smoke.mjs` 通過。
- `python -m compileall -q src/menu_planner/api/auth src/menu_planner/api/main.py src/menu_planner/api/routes/admin_catalog.py` 通過。
- 使用 `uvicorn` 啟動後，以 `curl` 驗證註冊、登入、`/v1/auth/me` 與 `/admin` 頁面；並確認 `/admin` HTML 不含 Admin Key 相關文字。
- Playwright Chromium 安裝仍受 apt/proxy HTTP 403 限制，無法產生瀏覽器截圖；已用 curl 與 UI static 測試提供替代證據。

### 重要結論

- 管理端寫入權限現在只有一條路徑：使用 active superuser 帳號登入後，以 Bearer token 呼叫 API。
