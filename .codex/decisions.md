# Technical Decisions
## 2026-06-08 Menu Export People Source

Decision:
匯出菜單工作表時，優先使用已補齊的採購資料中的人數資訊。

Reason:
保留使用者於 UI 中逐日調整的人數設定。

Fallback:
若無採購資料，則使用設定檔中的人數配置。

---

## 2026-06-08 Excel Auto-fit Strategy

Decision:
由 Python 端估算欄寬並自動調整。

Rules:
- 東亞全形字元視為 2 字元寬度
- 半形字元視為 1 字元寬度
- 超長欄位套用最大寬度限制

Reason:
避免 JSON 或說明文字造成 Excel 欄位過寬。

---

## 2026-06-08 Result Table Column Visibility

Decision:
採用前端顯示控制，不重新產生菜單資料。

Implementation:
- data-result-column
- Checkbox 控制顯示狀態

Reason:
避免影響實際菜單結果資料。

---

## 2026-06-08 Column Visibility Persistence

Decision:
使用 localStorage 保存欄位顯示偏好。

Storage Key:
menuPlanner.resultTable.hiddenColumns

Reason:
保留使用者設定，避免重新整理頁面後遺失。

---

## 2026-06-08 Account Management and Admin Authorization

Decision:
導入本機 JSON user store + PBKDF2 密碼雜湊 + HMAC Bearer token 的帳號系統；此初始決策曾以 `superuser` 作為管理寫入 API 的主要權限，後續已由 active data editor 與 backup_manager 決策取代部分範圍。

Reason:
原本 `MENU_ADMIN_KEY` 只是一組共享密鑰，無法審核個別帳號、區分角色或追蹤使用者狀態。帳號系統可提供 pending/active/rejected 流程與使用者管理。

Authorization:
初始版本管理寫入 API 以 active superuser Bearer token 作為唯一授權方式；目前資料維護已改由 active user，備份還原/刪除由 backup_manager 或 superuser，帳號管理仍由 superuser。

Bootstrap:
當 user store 為空時，第一個註冊帳號自動成為 active superuser，避免沒有 bootstrap 檔或環境變數時鎖死管理流程。

Security Note:
`.auth_users.json` 視為本機敏感資料，只保存 password hash 仍不得提交至版本庫。

Long-term Consideration:
多 worker、多副本或正式多使用者部署應改用資料庫 user table 或集中式 auth provider，而不是本機 JSON 檔。

---

## 2026-06-08 Remove X-Admin-Key Compatibility

Decision:
移除 `X-Admin-Key` / `MENU_ADMIN_KEY` 相容授權，管理寫入 API 只接受 active superuser Bearer token。

Reason:
舊版 Admin Key 尚未實際使用；保留共享密鑰會增加 UI 與後端授權路徑複雜度，也不利於後續以帳號審核與角色追蹤作為唯一權限模型。

Rejected Alternative:
不保留「superuser token 或 Admin Key 皆可」的雙軌授權，以避免使用者混淆與測試矩陣擴大。

Long-term Consideration:
若未來需要服務間或自動化寫入權限，應新增可審計的 service account / API token 模型，而不是恢復共享 Admin Key。

---

## 2026-06-08 Auth Store Serverless Fallback

Decision:
未顯式設定 `AUTH_USERS_FILE` 時，`AuthStore` 若無法寫入預設專案根目錄 `.auth_users.json`，會 fallback 到系統暫存目錄下的 `menu-planner/.auth_users.json`。

Reason:
Vercel Serverless 等部署環境可能在 import-time 對專案目錄唯讀；帳號系統在模組載入時建立 user store 會導致整個 Serverless Function 啟動失敗。Fallback 可讓服務先正常啟動。

Explicit Path Rule:
若 `AUTH_USERS_FILE` 或建構子 path 已顯式指定，寫入失敗不 fallback，保留錯誤以提醒部署設定或權限問題。

Long-term Consideration:
暫存目錄 fallback 不是持久化方案；正式部署應遷移到 SQLite/Postgres/KV/Blob 或外部身份服務，以支援多實例一致性與資料保存。

---

## 2026-06-08 Active User Data Editor Permission

Decision:
資料庫資料維護操作改為 active user 即可執行，不再要求 superuser。

Scope:
- 食材、菜色、價格、庫存、單位換算、菜色食材清單與庫存食材合併。
- 手動建立備份與備份註解。

Backup Manager Scope:
- 備份還原、單一備份刪除與批次備份刪除由 `backup_manager` 或 `superuser` 執行。

Superuser-only Scope:
- 帳號審核、拒絕與刪除。

Reason:
資料維護人員需要能完善資料，但不應因此取得帳號管理或刪除備份等高風險權限。建立備份有助於資料處理作業安全；刪除與還原備份可能造成無法回復或覆蓋現況，因此拆出備份管理員，避免授予完整 superuser。

Rejected Alternative:
不採用「所有寫入都必須 superuser」；此方案會迫使資料維護者取得過強權限。

---

## 2026-06-08 Dedicated Account Management Page

Decision:
帳號登入、註冊、審核與權限說明獨立到 `account.html`，並在全站導覽列加入帳號管理入口與登入身分摘要。

Reason:
帳號管理與資料庫管理是不同工作脈絡。獨立頁面可降低資料維護頁資訊負擔，也讓使用者更容易知道自己目前權限。

---

## 2026-06-08 Backup Manager Role

Decision:
新增 `backup_manager` 角色，作為高於普通資料維護者、低於完整 `superuser` 的備份管理權限。

Authorization:
- `backup_manager` 與 `superuser` 可還原備份、刪除單一備份與批次刪除備份。
- `backup_manager` 同時具備 active data editor 能力，可執行普通帳號可做的資料維護與建立備份。
- 帳號審核、拒絕與刪除仍限定 `superuser`。

Reason:
備份檔還原與刪除是高風險操作，但不等同於完整帳號管理權限。將備份管理拆成獨立角色，可授權資料/備份處理者完成復原與清理作業，同時避免授予可審核或刪除帳號的 superuser 權限。

Rejected Alternative:
不採用「備份還原/刪除仍需 superuser」；這會迫使備份處理者取得過強帳號管理權限。

---

## 2026-06-16 Portable Auth Pack Security Alignment

Decision:
主程式 auth 模組跟進 `portable_auth_pack` 新版安全功能，採用 token jti/version、logout denylist、密碼變更/重設流程、登入稽核與節流機制。

Role Model:
採用新版階層 `data_reader < data_editor < db_operator < superuser`；因尚未部署生產系統，不保留舊角色 `user` / `manager` / `backup_manager` 相容映射，以降低授權模型複雜度。

Reason:
新版 pack 已補上 logout 失效、密碼生命週期、泛用登入錯誤、dummy password hash timing balance 與正式環境 secret fail-fast，比原本 Menu Planner auth 更安全完整。

Compatibility:
管理資料 API 直接使用新角色 dependency：資料維護使用 `require_data_editor`，危險備份操作使用 `require_db_operator`，帳號管理使用 `require_superuser`。

## 2026-06-16 Auth JSON Recovery and Browser-local Test Auth

Decision:
保留單檔 `.auth_users.json` 作為本機/單機 auth store，但新增壞檔備份還原保護：JSON decode 失敗時將原檔搬移為 `.corrupt-*.bak`，再重建空 store。第一個註冊帳號恢復自動成為 active superuser。

Reason:
`.auth_users.json` 同時保存 users、login_audit、password_reset_tokens 與 token_denylist；雖然 `login_audit` 已有筆數上限，但單檔 JSON 仍可能因磁碟/中斷/手動編輯造成壞檔，因此需要基礎防壞檔機制。

Decision:
為避免正式環境被濫用，browser-local auth test mode 不再自動啟用；必須同時符合 Vercel preview/development、未設定 `AUTH_USERS_FILE`、且 `AUTH_BROWSER_LOCAL_STORE=1`。Vercel production、非 Vercel 或顯式 `AUTH_BROWSER_LOCAL_STORE=0` 一律停用。

Reason:
Vercel Serverless 檔案系統不適合持久保存 `.auth_users.json`。browser-local 模式讓部署測試者可在瀏覽器 localStorage 建立測試帳號並取得後端簽章 token，以驗證 UI 與權限流程。

Security Note:
browser-local auth test mode 不適合正式部署；帳號資料由瀏覽器持有，且 token 簽發信任瀏覽器提供的 active user/role。正式部署應設定持久化 auth store 或改用資料庫/KV/外部身份服務。

## 2026-06-16 Auth Store Versioned Backups and Split Audit Log

Decision:
帳號主檔 `.auth_users.json` 維持 JSON store，但每次寫入前先建立多版本備份到 `<auth_file>.versions/`，並將登入/註冊 audit 分流到 `<auth_file>.login_audit.jsonl`。

Reason:
帳號主檔保存 users、reset token 與 denylist，屬於較低頻但高價值狀態；登入 audit 是高頻追加事件。分流可降低主帳號檔膨脹與每次登入都重寫整份帳號 JSON 的風險。多版本備份則補強誤寫、遷移或非壞檔情境下的回復能力。

Compatibility:
`GET /v1/auth/login-audit` 對外 API 不變。若舊帳號 JSON 內仍有 `login_audit` 陣列，AuthStore 初始化時會遷移到 JSONL 並從主檔移除。

Long-term Consideration:
這仍是本機檔案型方案；多 worker、多副本或正式多使用者部署應遷移到資料庫/KV/外部身份服務，並把 audit 放入專用 append-only log/table。
