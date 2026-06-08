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