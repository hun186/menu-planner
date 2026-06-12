# Backlog

- 建立 Playwright 瀏覽器快取或替代下載來源，解決受 Proxy/CDN 限制環境的瀏覽器安裝問題。
- 更新或移除 `tests/ui_static/test_index_allowed_weekdays.mjs` 中過時的靜態驗證條件，使 UI Static 測試恢復全數通過。
- 評估於規劃結果表格新增「顯示所有欄位」功能，方便使用者快速還原隱藏欄位。
- 將本機 JSON auth store 遷移到 SQLite 或既有資料庫 schema，支援多 worker / 多副本一致性。
- 補上帳號變更密碼、重設密碼、token denylist/logout 失效與登入稽核紀錄。
- 建立可用的 API integration 測試策略，解決目前 TestClient 需要 `httpx2` 但環境無法安裝的問題。
- 為帳號管理 UI 補 Playwright 視覺驗證；目前 Chromium 安裝受 HTTP 403 限制。
- 若未來需要自動化寫入 API，設計可審計且可撤銷的 service account / API token，不恢復共享 Admin Key。
- 為 Vercel/Serverless 部署新增正式持久化 auth store（例如 Postgres、KV 或集中式 auth provider），取代目前只用來避免崩潰的 `/tmp` fallback。
- 在部署文件補充 `AUTH_SECRET`、bootstrap superuser 與正式 auth storage 的 Vercel 環境變數設定指南。

- 待 Playwright Chromium 下載/系統依賴安裝問題解決後，補做帳號管理頁權限說明 tooltip hover 截圖驗證。
- 評估是否將 `manager` 與 `user` 進一步拆分；目前兩者同屬 active data editor，差異主要保留給未來細分流程。