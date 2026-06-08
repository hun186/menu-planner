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
導入本機 JSON user store + PBKDF2 密碼雜湊 + HMAC Bearer token 的帳號系統，並以 `superuser` 作為管理寫入 API 的主要權限。

Reason:
原本 `MENU_ADMIN_KEY` 只是一組共享密鑰，無法審核個別帳號、區分角色或追蹤使用者狀態。帳號系統可提供 pending/active/rejected 流程與使用者管理。

Authorization:
管理寫入 API 以 active superuser Bearer token 作為唯一授權方式。

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
