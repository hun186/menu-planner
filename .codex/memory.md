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

## 2026-06-08 Vercel Auth Store Crash Fix

### 任務目的

- 修正導入帳號管理系統後，Vercel Serverless Function 在部署環境啟動時可能因預設 auth user store 寫入專案目錄而崩潰的問題。

### 主要修改內容

- `AuthStore` 初始化改為先嘗試使用預設 `.auth_users.json`；若未顯式設定 `AUTH_USERS_FILE` 且預設位置不可寫，會退回作業系統暫存目錄中的 ephemeral auth store。
- 若使用者顯式設定 `AUTH_USERS_FILE`，寫入錯誤仍會直接拋出，避免設定錯誤被靜默掩蓋。
- 新增單元測試覆蓋「預設路徑不可寫時 fallback」與「顯式路徑不可寫時不 fallback」。

### 驗證結果

- `python -c "import fastapi, pytest"` 通過。
- `PYTHONPATH=. pytest -q tests/unit/test_auth_system.py` 通過，4 tests passed。
- `python -m compileall -q src/menu_planner/api/auth/auth_store.py src/menu_planner/api/auth/dependencies.py src/menu_planner/api/auth/router.py api/index.py` 通過。
- 使用 `AUTH_USERS_FILE` 指向暫存檔啟動 `uvicorn`，並以 `curl` 呼叫 `/v1/auth/users`，服務正常回應 401 Unauthorized，確認 auth router 可啟動且未發生 server crash。

### 重要結論

- Vercel 或其他唯讀部署環境不應在 import-time 強制寫入專案根目錄；預設 fallback 可避免啟動即崩潰。
- `/tmp` 類暫存 auth store 只適合避免 serverless crash，不適合作為長期帳號資料保存方式。

## 2026-06-08 Role Permission and Account Page Update

### 任務目的

- 回答並落實帳號權限分層：訪客、普通帳號、超級管理者的可用功能需更清楚，並降低資料維護人員不必要取得 superuser 的風險。

### 主要修改內容

- 新增 active user 等級的資料維護授權 dependency，讓已啟用的普通帳號可維護資料庫內容。
- 將食材、菜色、價格、庫存、單位換算、菜色食材清單、庫存食材合併、手動建立備份與備份註解改為 active user 即可執行。
- 保留帳號審核為 superuser 權限；備份還原、單一備份刪除與批次備份刪除後續已拆給 backup_manager 或 superuser。
- 新增獨立帳號管理頁，包含登入、註冊、帳號審核與權限說明區塊；資料庫管理頁改回專注資料庫與備份作業。
- 導航列新增帳號管理入口，並顯示目前登入帳號與帳號等級；未登入時顯示訪客狀態。

### 驗證結果

- 相關 Node UI static 測試通過。
- 相關 Python unit 測試通過。
- 本機啟動 FastAPI 後，以 HTTP 讀取 `/account.html`、`/admin`、`/` 均可取得新頁面/導覽內容。
- 完整 UI static suite 仍有既有 `test_index_allowed_weekdays.mjs` 2 項失敗，與本次帳號/權限修改無關。
- Playwright Chromium 仍因 Proxy/CDN HTTP 403 無法安裝，因此無法產生 hover 截圖；已用靜態測試與 HTTP 頁面檢查作為替代證據。

### 重要結論

- 「完善資料」不再需要發 superuser；一般已啟用帳號即可處理資料維護與建立備份。
- 具破壞性或不可逆風險較高的備份還原/刪除，後續已拆給備份管理員或 superuser；帳號管理仍需 superuser。

## 2026-06-08 Backup Manager Role

### 任務目的

- 依使用者回饋，將備份還原與刪除從完整 superuser 權限拆出，新增介於普通帳號與 superuser 之間的「備份管理員」。

### 主要修改內容

- 新增 `backup_manager` 角色，帳號審核時可指派。
- 新增 `require_backup_manager` 授權 dependency，允許 `backup_manager` 與 `superuser` 執行高風險備份操作。
- 備份還原、單一備份刪除與批次備份刪除改由備份管理員或 superuser 執行，不再要求完整 superuser。
- 備份管理員仍可執行普通已啟用帳號可做的資料維護操作，但不能審核、拒絕或刪除帳號。
- 帳號管理頁、導覽列角色標籤與資料庫管理頁權限文案已加入備份管理員說明。

### 驗證結果

- 相關 Node UI static 測試通過。
- 相關 Python unit 測試通過。
- 本機啟動 FastAPI 後，以 HTTP 讀取 `/account.html`、`/admin`、`/` 均可取得備份管理員與新權限文案。
- Playwright Chromium 下載仍因 CDN HTTP 403 無法完成，未能產生 hover 截圖；以靜態測試與 HTTP 頁面檢查作為替代證據。

### 重要結論

- 現在權限層級為：訪客 < active user/manager < backup_manager < superuser。
- `backup_manager` 可管理備份檔並維護資料，但不具帳號審核能力。

## 2026-06-16 Portable Auth Pack Upgrade Import

### 任務目的

- 將 `portable_auth_pack` 範例包新增的安全與帳號功能導入主程式既有 auth 模組。

### 主要修改內容

- 將 auth router 拆分為 `auth_routes`、`usage_routes`、`auth_support`、`auth_tokens`、`auth_logging`，並保留主程式 include 的聚合 `router`。
- 新增正式環境 `AUTH_SECRET` 長度檢查、token jti/version、logout denylist、密碼變更、管理員重設密碼、使用者一次性 reset token、忘記密碼泛用回應、登入/註冊/重設節流與登入稽核。
- 導入新版角色階層：`data_reader < data_editor < db_operator < superuser`；後續已依使用者指示移除舊角色 `user` / `manager` / `backup_manager` 相容映射。
- 保留 Menu Planner 既有 Vercel/serverless auth store fallback，避免預設 `.auth_users.json` 不可寫時啟動崩潰。
- 帳號頁新增變更密碼、忘記密碼、使用 token 重設密碼與 superuser 產生 reset token 的 UI 入口。

### 驗證結果

- `python -c "import fastapi, pytest, openpyxl"` 通過。
- `PYTHONPATH=. pytest -q tests/unit/test_auth_system.py tests/unit/test_admin_catalog_read_routes_auth.py` 通過，8 tests passed。
- `node --check src/menu_planner/ui_static/account.js && node --check src/menu_planner/ui_static/admin/api.js` 通過。
- `node tests/ui_static/test_admin_auth_panel.mjs && node tests/ui_static/test_admin_smoke.mjs` 通過。
- `python -m compileall -q src/menu_planner/api/auth src/menu_planner/api/routes/admin_catalog.py` 通過。

### 重要結論

- 主程式 auth 功能已與 portable auth pack 的新增安全功能對齊，同時保留舊角色名稱與既有 route dependency 名稱的相容性。

## 2026-06-16 Remove Legacy Auth Role Aliases

### 任務目的

- 因 auth upgrade 尚未部署生產系統，依使用者指示移除舊角色 `user` / `manager` / `backup_manager` 相容映射，直接採用新版角色模型。

### 主要修改內容

- Auth role normalization 不再接受舊角色別名；approve role 僅允許 `data_reader`、`data_editor`、`db_operator`、`superuser`。
- 管理備份危險操作改用 `require_db_operator` dependency，帳號管理測試改用 `require_superuser`。
- 帳號頁、導覽列與舊管理頁殘留角色選單改為新角色文案與值。

### 驗證結果

- `PYTHONPATH=. pytest -q tests/unit/test_auth_system.py tests/unit/test_admin_catalog_read_routes_auth.py` 通過。
- `node --check src/menu_planner/ui_static/account.js && node --check src/menu_planner/ui_static/admin/api.js && node --check src/menu_planner/ui_static/admin.js && node --check src/menu_planner/ui_static/nav.js` 通過。
- `node tests/ui_static/test_admin_auth_panel.mjs && node tests/ui_static/test_admin_smoke.mjs` 通過。
- `python -m compileall -q src/menu_planner/api/auth src/menu_planner/api/routes/admin_catalog.py` 通過。

### 重要結論

- 新部署只需處理 `data_reader`、`data_editor`、`db_operator`、`superuser` 四種角色，避免舊角色別名造成文件、UI 與授權判斷混淆。
