menu-planner/
├─ README.md
├─ pyproject.toml
├─ .gitignore
├─ LICENSE
│
├─ data/
│  ├─ mock_menu_dataset.json          # 你要的模擬資料集（菜色/食材/庫存/時價）
│  └─ menu.db                         # 轉完的 SQLite（可選：可不 commit）
│
├─ scripts/
│  ├─ json_to_sqlite.py               # JSON → SQLite 匯入程式（你剛剛要的那支）
│  └─ seed_db.sh                      # 一鍵初始化（可選）
│
├─ src/
│  └─ menu_planner/
│     ├─ __init__.py
│     │
│     ├─ db/
│     │  ├─ schema.sql                # DB schema（建議把 DDL 放這）
│     │  ├─ repo.py                   # 資料存取層（查菜色、查庫存、查價格…）
│     │  └─ queries.py                # 常用 SQL（可選）
│     │
│     ├─ config/
│     │  ├─ constraints.schema.json   # 限制條件 JSON schema（做 UI 驗證很重要）
│     │  ├─ defaults.json             # 預設限制條件（UI 開啟先載入）
│     │  └─ loader.py                 # 讀取/驗證/正規化 config
│     │
│     ├─ engine/
│     │  ├─ features.py               # 把 dish 轉成可計算特徵：成本、肉類、食材集合…
│     │  ├─ constraints.py            # Hard/Soft constraints 判斷與增量檢查
│     │  ├─ scoring.py                # 打分：成本、重複、庫存優先、口味平衡…
│     │  ├─ backtracking.py           # 回溯搜尋：先求可行解
│     │  ├─ local_search.py           # 局部搜尋：交換/替換微調降分
│     │  ├─ explain.py                # 可解釋輸出：每一天為什麼選這些菜、扣分明細
│     │  └─ planner.py                # 對外入口：plan_month(...)
│     │
│     ├─ api/
│     │  ├─ main.py                   # FastAPI/Flask 入口（提供 UI 後端）
│     │  ├─ routes_catalog.py         # 菜色/食材/價格查詢
│     │  ├─ routes_config.py          # config 讀寫/驗證
│     │  └─ routes_plan.py            # /plan 產生排程 + /explain 回傳理由
│     │
│     └─ ui_static/
│        ├─ index.html                # UI（純 HTML + jQuery）
│        ├─ app.js                    # 組表單、預覽 JSON、呼叫 /plan
│        └─ styles.css
│
├─ tests/
│  ├─ test_import_db.py               # JSON→SQLite 是否正確
│  ├─ test_constraints.py             # 硬限制檢查
│  └─ test_planner_small.py           # 小範圍排程可重現
│
└─ .github/
   └─ workflows/
      └─ ci.yml                       # 自動跑測試
