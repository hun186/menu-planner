# Refactor Audit（初步）

> 目的：針對目前可見程式碼，先找出「最值得先重構」的區塊，降低維護成本與回歸風險。

## P0（最優先）

### 1) `planner.py` 單一函式負責過多流程
- `plan_month` 同時做了：設定解析、資料讀取、特徵建構、主菜排程、補齊配菜/湯/水果、local search、debug 包裝與輸出整理。
- 函式很長，且包含多段條件分支，後續每加一條規則都容易產生連鎖改動。
- 檔內也混有直接 `print` 偵錯輸出（例如菜色數量統計），不利於正式環境追蹤與測試隔離。

**建議**
1. 拆成 pipeline：`prepare_context` / `run_backtracking` / `run_local_search` / `build_result`。
2. 將 debug 欄位建立抽成 `build_debug_info(...)`。
3. 用 logging 取代 `print`，並在 API 層控制 log level。

## P1（高優先）

### 2) API `main.py` 有重複流程與錯誤處理策略不一致
- `/plan` 與 `/export/excel` 都重複做 `validate_config` 與 `plan_month` 呼叫。
- `/plan` 回傳 `{ok:false, errors:[...]}`，`/export/excel` 改用 `HTTPException`；錯誤格式不一致，前端整合需要分流處理。

**建議**
1. 抽一層共用服務（例如 `run_plan_or_raise`）。
2. 統一錯誤模型（可考慮全部走 HTTP status + 統一 JSON body）。
3. 將 `db_path` 建立 repo 的流程改成 dependency injection（FastAPI `Depends`），方便測試替身（mock repo）。

### 3) `ui_static/app.js` 單檔過大，狀態與 UI 強耦合
- 同一檔案同時處理 API、表單狀態、分數解釋、渲染、搜尋建議、錯誤顯示。
- 大量共用全域狀態（`baseDefaults`, `ING`, `DISHES`, `lastCfg`, `lastResult`）會讓後續功能加入時互相影響。

**建議**
1. 至少拆成：`api.js` / `state.js` / `render.js` / `score_explain.js`。
2. 將 `cfg` 轉換邏輯獨立成純函式模組（便於單元測試）。
3. 將 jQuery selector 與 DOM id 整理成常數表，減少魔法字串。

### 4) `ui_static/admin.js` 與 `app.js` 存在相同問題
- API 包裝、錯誤處理、escapeHtml、catalog 載入/快取等邏輯與 `app.js` 類似但未共用。
- CRUD 操作與 modal 控制都在同檔，閱讀與修改成本高。

**建議**
1. 抽 shared util（`http`, `html`, `catalog cache`）。
2. 按 domain 拆模組：ingredients / dishes / pricing-inventory。
3. 先補 smoke test（至少 API mock + 主要事件流）再拆檔，降低回歸風險。

## P2（中優先）

### 5) `repo.py` 可再抽象化，減少重複 mapping code
- 多個 `fetch_*` 都是「查詢 -> row to dataclass」的相似模板。
- `fetch_dishes` 內部才 `import json`，風格不一致，也不利於靜態分析工具。

**建議**
1. 模組頂端統一 import，並引入小型 row mapper helper。
2. 把 SQL 字串集中（常數/查詢物件）避免散落，提升可讀性與可測性。
3. 為價格查詢加索引需求註解（`ingredient_id, price_date`）避免日後資料量上升退化。

## 建議落地順序（兩週示意）
1. **第 1 週**：先重構 `planner.py`（不改行為），補 3~5 個 golden test。
2. **第 2 週**：統一 API 錯誤模型 + 前端 `app.js` 拆出 `api/state`。
3. `admin.js` 與 `repo.py` 放到第三階段，避免一次改太大。

## 驗收基準（Definition of Done）
- 同一組 seed 與 config，排程結果（主菜/配菜組合）不變。
- `/plan` 與 `/export/excel` 的錯誤 JSON 結構一致。
- 前端拆檔後，既有手動流程（載入設定、驗證、產生、匯出）全數可用。
