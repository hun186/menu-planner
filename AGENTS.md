# Agent 工作指南

此檔提供 Codex / Agent 修改本 Repo 時的優先參考資訊。

目標：

* 減少不必要的全專案探索
* 降低 Token 消耗
* 提高修改效率
* 保持架構一致性
* 累積長期專案記憶

---

# 專案上下文載入（Project Context Loading）

在開始任何任務前，必須依序閱讀：

1. AGENTS.md
2. .codex/memory.md
3. .codex/architecture.md
4. .codex/api_contract.md
5. .codex/known_issues.md
6. .codex/decisions.md
7. .codex/backlog.md

若上述檔案或目錄不存在：

1. 建立 `.codex/` 目錄
2. 建立缺少的檔案
3. 以適當標題初始化內容

上述檔案視為本專案的長期記憶（Persistent Project Memory）。

若文件內容與目前程式碼不一致：

* 以程式碼為準
* 更新相關文件

---

# 開發原則（Development Principles）

優先理解：

* 專案目標
* 系統架構
* 資料流
* 模組邊界
* API 契約
* 已知限制

避免在未理解架構前進行大規模修改。

優先重用現有實作。

避免建立重複功能。

保持與既有程式風格一致。

---

# 開發流程（Development Workflow）

所有功能開發遵循：

1. 需求分析
2. 架構分析
3. 核心資料模型與介面設計
4. 功能實作
5. 驗證
6. 記憶更新

依專案類型可包含：

* Domain Model
* API
* Database
* Agent Workflow
* Batch Job
* CLI
* Frontend UI
* Infrastructure
* Docker
* CI/CD

僅實作本專案實際需要的組件。

不得為符合流程而新增不必要模組。

---

# 真實功能原則（Real Functionality First）

禁止以展示層、模擬資料或假結果掩蓋核心功能尚未完成的事實。

禁止使用：

* Mock Data
* Hard-coded Output
* Fake Success Message
* Stub Result

來宣稱功能已完成。

若因開發需要暫時保留未完成實作，必須明確標註：

STUB IMPLEMENTATION

並同步記錄於：

`.codex/backlog.md`

---

# 驗證原則（Verification Requirements）

任務完成前必須提供驗證證據。

依專案性質至少包含一項：

* Unit Test
* Integration Test
* API Test
* SQL Query 驗證
* CLI 執行結果
* Batch Job 執行結果
* Agent Execution Log
* UI Static Test
* Playwright 測試
* Export File Validation
* Docker 啟動驗證
* curl 驗證

驗證結果需記錄於：

`.codex/memory.md`

---

# 無法驗證時的處理方式

若因以下原因無法完成驗證：

* Sandbox 限制
* 網路限制
* 權限限制
* 第三方服務限制
* 瀏覽器限制
* 套件安裝限制
* Docker 環境限制

必須：

1. 明確說明原因
2. 提供替代驗證方式
3. 更新 `.codex/known_issues.md`

未提供驗證說明前，不得宣稱任務完成。

---

# 專案記憶維護（Memory Maintenance）

每次完成任務後，必須同步更新專案記憶：

1. 更新 `.codex/memory.md`
2. 若架構、模組邊界或資料流有變更，更新 `.codex/architecture.md`
3. 若 API Contract 有變更，更新 `.codex/api_contract.md`
4. 若發現新的環境限制、錯誤或已知問題，更新 `.codex/known_issues.md`
5. 若產生新的設計決策或架構決策，更新 `.codex/decisions.md`
6. 若發現後續待辦事項或改善建議，更新 `.codex/backlog.md`

保留歷史紀錄。

一般任務僅追加內容。

一般任務不得覆蓋既有紀錄；但「記憶濃縮」是唯一例外，必須依下方濃縮機制保留可追溯歸檔後，才可重寫 active memory 檔案。

---

# 記憶濃縮機制（Memory Compaction）

長期記憶的目標是降低 token 消耗，而不是保存所有逐字流水帳。當記憶檔過長時，應把 active memory 維持為「目前仍有用的摘要」，並將完整歷史移入歸檔。

## 觸發條件

任一 `.codex/*.md` active memory 檔案符合下列條件之一時，必須在當次任務的「記憶更新」階段執行濃縮；若任務本身就是整理記憶，則應優先執行：

* 單檔超過 400 行。
* 單檔超過 40 KB。
* 單檔累積超過 20 個日期區塊或工作紀錄區塊。
* 已有多筆內容被目前程式碼、決策或 API contract 明確取代。
* 閱讀 active memory 時發現大量重複、過時或低價值執行細節。

## 濃縮流程

1. 建立 `.codex/archive/`（若不存在）。
2. 先將濃縮前全文保存到 `.codex/archive/<原檔名>-YYYYMMDD-HHMMSS.md`。
3. 重寫原 active memory 檔案為精簡版本，建議結構如下：
   * `# <檔案主題>`
   * `## Current Summary`：目前仍有效的結論、架構、限制或待辦。
   * `## Recent Changes`：保留最近 5～10 筆仍有參考價值的變更摘要。
   * `## Archived History`：列出歸檔檔名、濃縮時間與涵蓋範圍。
4. 濃縮時必須保留尚未解決的 backlog、known issues、STUB IMPLEMENTATION、API contract 與仍有效的架構決策。
5. 已失效內容不要逐字搬回 active memory；只需以「已被 X 取代」或「歷史細節已歸檔」記錄。
6. 濃縮完成後，在 `.codex/memory.md` 追加一筆濃縮紀錄，說明濃縮了哪些檔案、歸檔位置與驗證方式。

## 濃縮後的載入規則

* 一般任務只需閱讀 active memory 檔案，不需主動讀取 `.codex/archive/`。
* 只有在使用者要求追溯歷史、active memory 指向特定歸檔、或需要釐清被濃縮前的細節時，才讀取相關歸檔檔案。
* 濃縮後 active memory 目標大小：每個檔案盡量低於 200 行；若內容本質上較複雜，可保留必要資訊但要移除流水帳。
* 歸檔檔案僅供追溯，不列入例行「專案上下文載入」。

---

# 記錄原則

## memory.md

記錄：

* 任務目的
* 主要修改內容
* 驗證結果
* 重要結論

避免記錄：

* 大量重複日誌
* 無意義執行細節

---

## architecture.md

記錄：

* 系統架構
* 模組關係
* 資料流
* 專案目錄結構
* 核心元件說明

---

## api_contract.md

記錄：

* API 路由
* Request 格式
* Response 格式
* 重要資料結構
* 對外介面契約

若專案無 API，可保留空白並註明：

「本專案目前無 API Contract。」

---

## known_issues.md

記錄：

* 已知錯誤
* 環境限制
* 外部服務限制
* Sandbox 限制
* Docker 問題
* Playwright 問題
* 資料庫問題

---

## decisions.md

記錄：

* 架構決策
* 技術選型原因
* 不採用方案及理由
* 長期維護考量

---

## backlog.md

記錄：

* 尚未完成事項
* 技術債
* 改善建議
* 未完成的 STUB IMPLEMENTATION

---

# 安全規範

禁止將以下資訊寫入任何記憶檔案：

* API Key
* Access Token
* Password
* Cookie
* Private Key
* 憑證內容
* 個人敏感資料
* 機密資訊

如發現敏感資訊，應立即排除並避免寫入記憶系統。

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

