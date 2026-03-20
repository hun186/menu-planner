# AGENTS.md

## Purpose
本專案要求 AI 助手在修改程式時，同時完成可驗證的開發與驗證流程。

## General Rules
1. 不要只修改程式，還要補上可驗證證據。
2. 若是前端可見行為變更，必須做 UI 驗證。
3. 優先沿用現有測試與啟動方式，不要任意改整套工具鏈。
4. 若環境限制導致無法直接顯示截圖，不可直接停止，必須提供替代證據。

## UI Validation Rules
凡是以下情況都視為前端可見變更：
- 文案變更
- tooltip / hover
- 按鈕、表格、欄位顯示
- 樣式或圖示狀態
- 表單互動

遇到前端可見變更時，請依序執行：
1. 啟動專案前端
2. 進入對應頁面
3. 重現互動行為
4. 優先用 Playwright 或既有 UI 測試驗證
5. 能截圖就截圖，輸出到 `artifacts/` 或測試指定目錄

## Tooltip / Hover Rules
若功能包含 tooltip、hover、title 屬性、警示說明：
1. 必須驗證滑鼠移入後的實際顯示內容
2. 回報中必須列出 tooltip 實際文字或範例
3. 若可行，需附 hover 狀態截圖

## Fallback Evidence
若當前環境無法直接截圖，至少必須提供：
- 修改檔案清單
- 關鍵 diff 說明
- 本地重現步驟
- 測試結果
- 畫面預期行為
- tooltip / hover 實際文字內容

禁止只回報：
- 無法截圖
- 無 browser container
- 無法附圖

## Reporting Format
每次完成任務後，固定使用以下格式：

- Summary
- Files changed
- Testing
- Screenshot
- Fallback evidence
- Risks / known issues

## Preferred Behavior
- 優先做最小可行修改
- 優先補最接近需求的測試
- 若已有失敗測試，區分是本次改動造成，還是既有問題
- 不要把既有測試失敗誤報成這次功能失敗