# Menu Planner（自動排菜單 PoC）

Menu Planner 是一個「可調限制條件、可解釋打分、可匯出 Excel」的自動排菜單系統。  
系統會根據資料庫中的食材、菜色、用量、價格、庫存與你設定的規則，產生每日菜單：

> **主菜 + 3 配菜 + 湯 + 水果**

並且支援「每週配額、避免連續同類型、禁用菜色、偏好食材、成本控制、庫存/到期偏好」等需求。

---

## 目錄結構（已依 repo 實際路徑校正）

```
menu-planner/
  .env
  API_CMD.txt
  data/
    menu.db
    mock_menu_dataset.json
    mock_menu_dataset_noodles.json
  scripts/
    json_to_sqlite.py
  src/
    menu_planner/
      api/
        main.py
        export_excel.py
        routes/
          admin_catalog.py
      config/
        defaults.json
        loader.py
      db/
        repo.py
        admin_repo.py
      engine/
        planner.py
        backtracking.py
        constraints.py
        scoring.py
        features.py
        explain.py
        local_search.py
        errors.py
      ui_static/
        index.html
        admin.html
        app.js
        admin.js
        styles.css
```

---

## 功能一覽

### 使用者端（排菜：`index.html`）
- 產生 N 天菜單（預設 30 天）
- 每日固定結構：主菜 + 三配菜 + 湯 + 水果
- 支援限制條件（表單與 JSON 可互相套用）
  - 成本區間（每人/日）
  - 主菜類型允許清單（例如：chicken/pork/beef/seafood/noodles/vegetarian）
  - 避免連續同類型（主菜）
  - 每週配額（主菜類型 weekly quota）
  - 偏好食材（多選）
  - 禁用菜色（搜尋加入）
  - 優先用庫存、優先用近到期（偏好策略）
- 可解釋打分（每日 cost、score、score breakdown、bonus/penalty、庫存使用明細）
- 匯出 Excel

### 管理端（資料庫管理：`admin.html`）
- 管理食材（CRUD）
- 管理菜色（CRUD）
- 維護「菜色食材用量」（ingredient + qty + unit）
- 維護食材庫存（快照：數量/單位/更新日/到期日）
- 維護食材價格（歷史：日期/單價/單位；逐列 Upsert）
- 管理權限（選配）：若後端設定 `MENU_ADMIN_KEY`，管理端需輸入金鑰才可寫入

---

## 安裝與啟動

### 1) 需求
- Python 3.10+（建議）
- SQLite（一般系統內建）
- 瀏覽器（前端為純 HTML + jQuery）

### 2) 建立虛擬環境並安裝依賴
> 若你 repo 有 `requirements.txt`，直接用；如果沒有，請依你實際依賴補上（至少會需要 fastapi、uvicorn、openpyxl 等）。

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\\Scripts\\activate

# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

### 3) 環境變數（選配）
你可以在 `.env` 或系統環境變數中設定：

- `MENU_DB_PATH`：資料庫路徑（預設建議 `data/menu.db`）
- `MENU_ADMIN_KEY`：管理端寫入金鑰（若不設定，admin 端可不填）

Windows（PowerShell）：
```powershell
$env:MENU_DB_PATH="data\\menu.db"
$env:MENU_ADMIN_KEY="your-secret"
```

macOS/Linux（bash）：
```bash
export MENU_DB_PATH="data/menu.db"
export MENU_ADMIN_KEY="your-secret"
```

### 4) 啟動後端（FastAPI）
API 入口位於：`src/menu_planner/api/main.py`

在 repo 根目錄執行（讓 Python 找得到 src）：

```bash
uvicorn src.menu_planner.api.main:app --host 0.0.0.0 --port 8000 --reload
```

> 若你的 `API_CMD.txt` 有指定啟動方式，以該檔為準；上面是最常見且與你路徑一致的啟動寫法。

### 5) 開啟前端
前端靜態檔位於：`src/menu_planner/ui_static/`

- 排菜（使用者端）：`src/menu_planner/ui_static/index.html`
- 管理（管理端）：`src/menu_planner/ui_static/admin.html`

若後端有提供靜態路由，通常可用：
- `http://localhost:8000/`（排菜）
- `http://localhost:8000/admin`（管理）

若沒有靜態路由，也可以直接用瀏覽器打開 `index.html` / `admin.html`（但需要注意 CORS 與 API URL 設定）。

---

## 快速開始（建議流程）

### A. 先準備資料庫
預設 DB：`data/menu.db`

如果你想從 mock dataset 重新灌入（JSON → SQLite）：
- `scripts/json_to_sqlite.py`
- `data/mock_menu_dataset.json`
- `data/mock_menu_dataset_noodles.json`

（請依腳本參數使用；若你希望我把 `json_to_sqlite.py` 的指令寫成 README 可直接複製執行版，貼一下該檔內容即可。）

### B. 排菜（index.html）
1. 設定「天數」與「成本區間（每人/日）」
2. 勾選「主菜類型允許」（雞/豬/牛/海鮮/麵食/素）
3. 設定「避免連續同類型」
4. 設定「每週配額（主菜）」
5. （選配）偏好食材（搜尋 → 點建議加入 chip）
6. （選配）禁用菜色（可先用角色過濾再搜尋）
7. 按 **驗證**
8. 按 **產生菜單**
9. 需要時按 **匯出 Excel**

### C. 管理資料（admin.html）
1. （選配）輸入 Admin Key 並儲存到本機
2. 食材管理：新增/編輯食材基本資料
3. 菜色管理：新增/編輯菜色（角色、主菜類型、菜系、標籤）
4. 編輯菜色食材：維護 ingredient + qty + unit
5. 價格/庫存：用 modal 維護該食材的庫存快照與歷史價格

---

## 資料模型（概念）

### 主要資料
- **Ingredient（食材）**：名稱、分類、蛋白群組、預設單位
- **Dish（菜色）**：名稱、角色（main/side/soup/fruit）、主菜類型（meat_type）、菜系、標籤
- **DishIngredient（菜色用量）**：某菜色用到哪些食材、用量 qty 與 unit
- **Price（價格歷史）**：食材價格（日期、單位）
- **Inventory（庫存快照）**：數量、單位、更新日、到期日
- **Unit Conversion（單位換算）**：用於用量 unit 與價格 unit 的換算

### DishFeatures（引擎計算特徵）
位置：`src/menu_planner/engine/features.py`

每道菜會在排程前被計算出：
- `cost_per_serving`：以食材用量 × 最新價格（含單位換算）
- `inventory_hit_ratio`：菜色用到庫存食材的比例（粗估）
- `near_expiry_days_min`：用到的庫存食材中，最近到期的剩餘天數
- `used_inventory_ingredients`：實際命中的庫存食材清單

---

## 限制條件（JSON / 表單對應）

前端提供「限制條件 JSON（可直接編輯）」：
- 表單變更會同步 JSON
- JSON 可再套用回表單

常見 hard 欄位（名稱以引擎使用為準）：
- `allowed_main_meat_types`：允許的主菜類型（例如 chicken/pork/beef/seafood/noodles/vegetarian）
- `no_consecutive_same_main_meat`：避免連續同主菜類型
- `weekly_max_main_meat`：每週主菜類型上限（配額）
- `exclude_dish_ids`：禁用菜色 ID
- `repeat_limits`：重複視窗限制（例如 7 天湯/配菜重複上限）
- `cost_range_per_person_per_day`：成本上下限

> 提醒：`meat_type` 雖名為肉類，但你 UI 也包含 noodles / vegetarian，本專案實際上把它視為「主菜類型」。請確保資料庫與規則使用同一套枚舉值，避免驗證失敗或配額失效。

---

## 可解釋結果（排程輸出）

結果會包含：
- 每日菜單（主菜/配菜/湯/水果）
- 每日成本 `cost`
- 每日分數 `score` 與拆解 `score_breakdown`
- `score_fitness = -score`（越高越好）
- 若排程失敗，該日會標記 failed 並給出原因與建議（例如成本超標、候選不足、重複限制太嚴）

---

## 常見問題（FAQ）

### Q1：為什麼我設定「海鮮每週上限 1 次」，一週內仍出現 2 次？
通常是以下原因之一：
1) **主菜類型未正規化**：例如蝦仁/魚被標成 `fish` / `shrimp`，但配額設在 `seafood`，就不會被同一類型統計。  
2) **週判定不一致**：排程端與計數端採用不同 week key（例如 day//7 vs ISO week），跨月/跨週時可能對不上。  
3) **非排程日 placeholder**：若週末/不排日以空值插入，計數更新邏輯必須確保只在 active day 計數。

建議做法：
- 針對 `Dish.meat_type` 做統一枚舉（chicken/pork/beef/seafood/noodles/vegetarian）
- 週配額統計使用「實際日期的 ISO week」（尤其跨月時更穩）
- 僅在「有主菜」的日子更新週計數

---

## License
（請填你的授權，例如 MIT）

## 貢獻方式
歡迎 Issue / PR：包含資料集擴充、規則擴充、UI 文案改善、排程效能與穩定性提升。
