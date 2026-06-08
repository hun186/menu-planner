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