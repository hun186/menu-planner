# AGENTS.md

## Purpose
本專案要求 AI 助手在修改程式時，同時完成「可驗證」的開發與驗證流程，而不是僅修改程式碼。

---

## General Rules
1. 不要只修改程式，還要補上可驗證證據。
2. 若是前端可見行為變更，必須做 UI 驗證。
3. 優先沿用現有測試與啟動方式，不要任意改整套工具鏈。
4. 若環境限制導致無法直接顯示截圖，不可直接停止，必須提供替代證據。
5. 不可只回報缺少套件或工具後就結束任務。

---

## Dependency & Environment Rules（新增）
執行任何測試或 UI 驗證前，必須確認環境可執行：

1. **不可只根據 requirements 檔判斷依賴已存在**
2. 必須實際驗證：
   - `python -c "import xxx"`
3. 若 import 失敗：
   - 依 repo 現有依賴管理方式安裝（requirements / pyproject / package.json）
4. 若為 Playwright：
   - 除 Python 套件外，需確認 browser binaries 是否可用
5. 若安裝失敗，需說明原因：
   - 套件缺失
   - browser 未安裝
   - sandbox / 權限限制
   - 網路或代理問題

禁止：
- 只說「缺少 playwright 套件」就停止

---

## Command Preference（新增）
執行驗證時，**優先使用 repo 既有命令**，依序：

1. `package.json` scripts
2. Makefile
3. `scripts/` 目錄內工具
4. `tests/` 內既有測試

禁止：
- 任意臨時發明一次性指令
- 直接寫一段未整合進 repo 的測試腳本（除非完全沒有既有機制）

---

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
4. 優先使用既有 UI 測試或 Playwright
5. 能截圖就截圖，輸出到 `artifacts/` 或測試目錄

---

## Tooltip / Hover Rules
若功能包含 tooltip、hover、title 屬性、警示說明：

1. 必須驗證滑鼠移入後的實際顯示內容
2. 回報中必須列出 tooltip 實際文字或範例
3. 若可行，需附 hover 狀態截圖

---

## Playwright Execution Rules（新增，重點）
若需使用 Playwright：

1. 先檢查：
   ```bash
   python -c "import playwright"