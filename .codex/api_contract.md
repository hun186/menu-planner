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
