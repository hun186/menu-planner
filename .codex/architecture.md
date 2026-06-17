# architecture


---

## 2026-06-11 XXXXX

- 
- 
- 
- 

---

## 2026-06-16 Auth Store Module Split

- `src/menu_planner/api/auth/auth_store.py`：保留帳號 domain 行為，包含註冊、審核、密碼變更/重設、token denylist、角色授權資料與登入節流狀態。
- `src/menu_planner/api/auth/auth_store_files.py`：負責本機檔案型 auth store 的 JSON 正規化、原子寫入、多版本備份、壞檔備份、inline audit 遷移與 JSONL audit append/list/prune。
- `AuthStore` 透過組合 `AuthStoreFiles` 存取檔案，避免帳號 domain method 直接承擔低階檔案 I/O 細節。
