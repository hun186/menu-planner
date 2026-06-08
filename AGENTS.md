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
   ```
2. 若 Python 套件不存在，先依 repo 既有依賴管理方式安裝 Playwright。
3. 確認 Chromium browser binaries 可用；若不可用，執行 Playwright browser 安裝命令。
4. 啟動前端後再執行 UI 驗證，並在完成後回報實際驗證命令與結果。

---

## Test commands

For frontend UI validation, run:

```bash
pip install playwright
python -m playwright install --with-deps chromium
npm install
npm run dev &
python -m playwright codegen
```

---

# Memory Persistence Rules

本專案使用 `memory.md` 作為長期任務記憶。

## Startup

每次開始任務時：

1. 優先閱讀：

   * README.md
   * AGENTS.md
   * memory.md（若存在）

2. 將 memory.md 視為歷史上下文：

   * 已完成事項
   * 設計決策
   * 已知限制
   * 技術債
   * 待辦事項

3. 若 memory.md 與目前程式碼不一致：

   * 以程式碼為準
   * 更新 memory.md

---

## Update Memory

完成任務後：

必須同步更新 `memory.md`

更新內容包含：

### Task

本次任務目的

### Changes

實際修改內容

### Verification

驗證方式與結果

### Decisions

重要設計決策

### Known Issues

尚未解決問題

### Next Suggestions

後續建議工作

---

## Append Policy

預設採用 Append 模式：

```md
## 2026-06-08 14:30

### Task
新增成本異常 Tooltip

### Changes
- 修改 cost_validator.py
- 修改 result_page.tsx

### Verification
- pytest 通過
- Playwright 驗證 Tooltip 顯示正常

### Decisions
維持原有成本計算邏輯

### Known Issues
Chromium 無法自動下載

### Next Suggestions
改為使用系統 Chromium
```

不要覆蓋歷史紀錄。

只在以下情況允許整理：

* memory.md 超過 2000 行
* 使用者要求整理

整理時保留：

* 重要決策
* 已知問題
* 架構資訊

刪除：

* 重複驗證紀錄
* 過期待辦事項

---

## Forbidden

禁止寫入：

* API Key
* Token
* Password
* Cookie
* 個資
* 機密資料

---

## Commit Rule

若本次任務修改程式：

應一併提交：

* code changes
* memory.md 更新

除非使用者明確要求不要修改 memory.md。
