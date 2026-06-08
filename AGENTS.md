# AGENTS.md

## 專案上下文載入（Project Context Loading）

在開始任何任務前，必須依序閱讀：

1. AGENTS.md
2. .codex/memory.md
3. .codex/known_issues.md
4. .codex/decisions.md
5. .codex/backlog.md

若上述檔案或目錄不存在：

1. 建立 `.codex/` 目錄
2. 建立缺少的檔案
3. 以適當標題初始化內容

上述檔案視為本專案的長期記憶（Persistent Project Memory）。

若文件內容與目前程式碼不一致：

* 以程式碼為準
* 更新相關記錄文件

---

## 專案記憶維護（Memory Maintenance）

每次完成任務後，必須同步更新專案記憶：

1. 更新 `.codex/memory.md`
2. 若發現新的環境限制、錯誤或已知問題，更新 `.codex/known_issues.md`
3. 若產生新的設計決策或架構決策，更新 `.codex/decisions.md`
4. 若發現後續待辦事項或改善建議，更新 `.codex/backlog.md`

不得略過記憶更新步驟。

專案記憶更新屬於任務的一部分。

在完成專案記憶更新前，不得視為任務已完成。

---

## 記錄原則

### memory.md

記錄：

* 任務目的
* 主要修改內容
* 驗證結果
* 重要結論

避免記錄：

* 大量重複日誌
* 無意義執行細節

---

### known_issues.md

記錄：

* 已知錯誤
* 環境限制
* 外部服務限制
* Sandbox 限制
* Playwright、Docker、資料庫等問題

---

### decisions.md

記錄：

* 架構決策
* 技術選型原因
* 不採用方案及理由
* 長期維護考量

---

### backlog.md

記錄：

* 尚未完成事項
* 後續優化建議
* 技術債
* 預計改善項目

---

禁止將以下資訊寫入任何記憶檔案：

* API Key
* Access Token
* Password
* Cookie
* 憑證內容
* 個人敏感資料
* 機密資訊

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

