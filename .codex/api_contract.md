# api contract


---

## 2026-06-11 XXXX

-
## 2026-06-16 Auth API Upgrade

- `POST /v1/auth/logout`：需 Bearer token；將目前 token 加入 denylist，回傳登出成功訊息。
- `POST /v1/auth/change-password`：需 Bearer token；body `{ current_password, new_password }`，成功後提升 `token_version` 使既有 token 失效。
- `POST /v1/auth/forgot-password`：公開端點；body `{ username }`，永遠回傳泛用訊息，不公開 reset token。
- `POST /v1/auth/reset-password`：公開端點；body `{ username, reset_token, new_password }`，使用 superuser 發出的有效一次性 token 重設密碼。
- `POST /v1/auth/users/{username}/password-reset-token`：需 superuser；產生一次性 reset token，應由安全管道交付使用者。
- `POST /v1/auth/users/{username}/reset-password`：需 superuser；body `{ new_password }`，直接重設指定使用者密碼。
- `GET /v1/auth/me` 與 `GET /v1/auth/users` 現在會附帶 `role_options`，角色階層為 `data_reader < data_editor < db_operator < superuser`；不再接受舊角色 `user` / `manager` / `backup_manager`。
- `GET /v1/editor/usage-stats`：需登入；回傳帳號登入稽核統計，普通使用者只能看自己的事件，superuser 可看全體/指定帳號。

## 2026-06-16 Auth Storage Mode API

- `GET /v1/auth/storage-mode`：公開端點；回傳 `{ mode, browser_local, message, role_options }`。只有在 Vercel preview/development、未設定 `AUTH_USERS_FILE` 且 `AUTH_BROWSER_LOCAL_STORE=1` 時才會回傳 `mode=browser_local`；Vercel production 與非 Vercel 環境會維持 server mode。
- `POST /v1/auth/browser-local-token`：僅在 browser-local 模式啟用；body `{ username, role, status }`，當 `status=active` 時簽發帶有 `mode=browser_local` 的 Bearer token。此端點只供唯讀部署測試，不應作為正式帳號驗證方案。

## 2026-06-16 Auth Store Split Audit Storage

- 既有 `GET /v1/auth/login-audit` API contract 不變；回傳仍為 `{ events, is_restricted_to_self }`。
- 後端儲存實作改為從分流 JSONL audit 檔讀取事件，不再依賴帳號主 JSON 內的 `login_audit` 陣列。
- 新增環境變數 `AUTH_LOGIN_AUDIT_FILE`：選配，用於指定登入/註冊 audit JSONL 路徑；未設定時預設為 `<AUTH_USERS_FILE>.login_audit.jsonl`。
