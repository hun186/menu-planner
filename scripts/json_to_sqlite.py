#scripts/json_to_sqlite.py
#cd D:\shared\TopicClassification\menu-planner
#python scripts/json_to_sqlite.py data/mock_menu_dataset.json data/menu.db
import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Iterable, Set, Optional
from datetime import datetime


DDL_INIT = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingredients (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  protein_group TEXT,
  default_unit TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dishes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('main','side','soup','fruit')),
  cuisine TEXT,
  meat_type TEXT,
  tags_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS dish_ingredients (
  dish_id TEXT NOT NULL,
  ingredient_id TEXT NOT NULL,
  qty REAL NOT NULL,
  unit TEXT NOT NULL,
  PRIMARY KEY (dish_id, ingredient_id),
  FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
  FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS ingredient_prices (
  ingredient_id TEXT NOT NULL,
  price_date TEXT NOT NULL,               -- YYYY-MM-DD
  price_per_unit REAL NOT NULL,
  unit TEXT NOT NULL,
  PRIMARY KEY (ingredient_id, price_date),
  FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventory (
  ingredient_id TEXT PRIMARY KEY,
  qty_on_hand REAL NOT NULL,
  unit TEXT NOT NULL,
  updated_at TEXT NOT NULL,               -- YYYY-MM-DD
  expiry_date TEXT,                       -- YYYY-MM-DD (nullable)
  FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS unit_conversions (
  from_unit TEXT NOT NULL,
  to_unit TEXT NOT NULL,
  factor REAL NOT NULL,
  PRIMARY KEY (from_unit, to_unit)
);

-- Indexes for faster query
CREATE INDEX IF NOT EXISTS idx_dishes_role ON dishes(role);
CREATE INDEX IF NOT EXISTS idx_dishes_meat_type ON dishes(meat_type);
CREATE INDEX IF NOT EXISTS idx_di_ingredient ON dish_ingredients(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_prices_date ON ingredient_prices(price_date);
"""


DDL_REBUILD = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS unit_conversions;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS ingredient_prices;
DROP TABLE IF EXISTS dish_ingredients;
DROP TABLE IF EXISTS dishes;
DROP TABLE IF EXISTS ingredients;
DROP TABLE IF EXISTS meta;
"""


def _as_text(v: Any) -> str:
  if v is None:
    return ""
  if isinstance(v, (dict, list)):
    return json.dumps(v, ensure_ascii=False)
  return str(v)


def load_json(path: Path) -> Dict[str, Any]:
  with path.open("r", encoding="utf-8") as f:
    return json.load(f)


def open_db(db_path: Path) -> sqlite3.Connection:
  conn = sqlite3.connect(str(db_path))
  conn.execute("PRAGMA foreign_keys = ON;")
  return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
  conn.executescript(DDL_INIT)


def rebuild_schema(conn: sqlite3.Connection) -> None:
  conn.executescript(DDL_REBUILD)
  conn.executescript(DDL_INIT)


def _chunked(seq: List[str], size: int = 900) -> Iterable[List[str]]:
  # SQLite 參數數量上限通常 999，留點餘裕
  for i in range(0, len(seq), size):
    yield seq[i:i+size]


def _existing_ids(conn: sqlite3.Connection, table: str, id_col: str, ids: Set[str]) -> Set[str]:
  if not ids:
    return set()
  found: Set[str] = set()
  id_list = list(ids)
  for chunk in _chunked(id_list):
    q = f"SELECT {id_col} FROM {table} WHERE {id_col} IN ({','.join(['?']*len(chunk))})"
    rows = conn.execute(q, chunk).fetchall()
    found.update(r[0] for r in rows)
  return found


def validate_dataset(conn: sqlite3.Connection, data: Dict[str, Any]) -> None:
  # 允許增量 JSON：缺少的區塊視為空
  ingredients = data.get("ingredients", []) or []
  dishes = data.get("dishes", []) or []
  prices = data.get("prices", []) or []
  inventory = data.get("inventory", []) or []
  unit_conversions = data.get("unit_conversions", []) or []

  # 檔案內重複檢查
  ing_ids = set()
  for ing in ingredients:
    if ing["id"] in ing_ids:
      raise ValueError(f"ingredients.id 重複：{ing['id']}")
    ing_ids.add(ing["id"])

  dish_ids = set()
  for dish in dishes:
    if dish["id"] in dish_ids:
      raise ValueError(f"dishes.id 重複：{dish['id']}")
    dish_ids.add(dish["id"])

  # 需要存在的食材 id（可能不在這次 JSON，但可能已在 DB）
  needed_ing_ids: Set[str] = set()

  for dish in dishes:
    for di in dish.get("ingredients", []) or []:
      needed_ing_ids.add(di["ingredient_id"])

  for inv in inventory:
    needed_ing_ids.add(inv["ingredient_id"])

  for p in prices:
    needed_ing_ids.add(p["ingredient_id"])

  # 如果引用的食材不在本檔，就必須已存在 DB
  missing_from_file = needed_ing_ids - ing_ids
  if missing_from_file:
    found_in_db = _existing_ids(conn, "ingredients", "id", missing_from_file)
    missing = missing_from_file - found_in_db
    if missing:
      raise ValueError(f"引用不存在的食材 id（檔案與 DB 都找不到）：{sorted(missing)}")

  # unit_conversions 形式檢查（簡單防呆）
  for c in unit_conversions:
    if c["factor"] is None:
      raise ValueError(f"unit_conversions.factor 不能為空：{c}")


def upsert_meta(conn: sqlite3.Connection, meta: Dict[str, Any]) -> None:
  if not meta:
    return
  rows = [(k, _as_text(v)) for k, v in meta.items()]
  conn.executemany("""
    INSERT INTO meta(key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value
  """, rows)


def upsert_unit_conversions(conn: sqlite3.Connection, convs: List[Dict[str, Any]]) -> None:
  if not convs:
    return
  rows = [(c["from_unit"], c["to_unit"], float(c["factor"])) for c in convs]
  conn.executemany("""
    INSERT INTO unit_conversions(from_unit, to_unit, factor) VALUES (?, ?, ?)
    ON CONFLICT(from_unit, to_unit) DO UPDATE SET factor=excluded.factor
  """, rows)


def upsert_ingredients(conn: sqlite3.Connection, ingredients: List[Dict[str, Any]]) -> None:
  if not ingredients:
    return
  rows = []
  for ing in ingredients:
    rows.append((
      ing["id"],
      ing["name"],
      ing["category"],
      ing.get("protein_group"),
      ing["default_unit"]
    ))
  conn.executemany("""
    INSERT INTO ingredients(id, name, category, protein_group, default_unit)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      name=excluded.name,
      category=excluded.category,
      protein_group=excluded.protein_group,
      default_unit=excluded.default_unit
  """, rows)


def upsert_dishes_and_links(
  conn: sqlite3.Connection,
  dishes: List[Dict[str, Any]],
  sync_dish_links: bool = False
) -> None:
  if not dishes:
    return

  dish_rows = []
  link_rows = []
  dish_ids = []

  for d in dishes:
    dish_ids.append(d["id"])
    dish_rows.append((
      d["id"],
      d["name"],
      d["role"],
      d.get("cuisine"),
      d.get("meat_type"),
      json.dumps(d.get("tags", []), ensure_ascii=False)
    ))
    for di in d.get("ingredients", []) or []:
      link_rows.append((
        d["id"],
        di["ingredient_id"],
        float(di["qty"]),
        di["unit"]
      ))

  conn.executemany("""
    INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
      name=excluded.name,
      role=excluded.role,
      cuisine=excluded.cuisine,
      meat_type=excluded.meat_type,
      tags_json=excluded.tags_json
  """, dish_rows)

  if sync_dish_links and dish_ids:
    conn.executemany("DELETE FROM dish_ingredients WHERE dish_id = ?", [(i,) for i in dish_ids])

  if link_rows:
    conn.executemany("""
      INSERT INTO dish_ingredients(dish_id, ingredient_id, qty, unit)
      VALUES (?, ?, ?, ?)
      ON CONFLICT(dish_id, ingredient_id) DO UPDATE SET
        qty=excluded.qty,
        unit=excluded.unit
    """, link_rows)


def upsert_prices(conn: sqlite3.Connection, prices: List[Dict[str, Any]]) -> None:
  if not prices:
    return
  rows = []
  for p in prices:
    rows.append((
      p["ingredient_id"],
      p["price_date"],
      float(p["price_per_unit"]),
      p["unit"]
    ))
  conn.executemany("""
    INSERT INTO ingredient_prices(ingredient_id, price_date, price_per_unit, unit)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(ingredient_id, price_date) DO UPDATE SET
      price_per_unit=excluded.price_per_unit,
      unit=excluded.unit
  """, rows)


def upsert_inventory(conn: sqlite3.Connection, inv_list: List[Dict[str, Any]]) -> None:
  if not inv_list:
    return
  rows = []
  for inv in inv_list:
    rows.append((
      inv["ingredient_id"],
      float(inv["qty_on_hand"]),
      inv["unit"],
      inv["updated_at"],
      inv.get("expiry_date")
    ))
  conn.executemany("""
    INSERT INTO inventory(ingredient_id, qty_on_hand, unit, updated_at, expiry_date)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT(ingredient_id) DO UPDATE SET
      qty_on_hand=excluded.qty_on_hand,
      unit=excluded.unit,
      updated_at=excluded.updated_at,
      expiry_date=excluded.expiry_date
  """, rows)


def main():
  parser = argparse.ArgumentParser(description="JSON → SQLite（支援增量匯入）")
  parser.add_argument("input_json", type=str, help="輸入 JSON 檔")
  parser.add_argument("output_db", type=str, help="輸出 / 目標 SQLite DB 檔")
  parser.add_argument("--mode", choices=["upsert", "rebuild"], default="upsert",
                      help="upsert：保留舊資料、增量新增/更新；rebuild：重建並清空資料")
  parser.add_argument("--sync-dish-links", action="store_true",
                      help="以本次 JSON 的 dish.ingredients 覆蓋該 dish 的食材連結（會先刪再寫）")
  args = parser.parse_args()

  json_path = Path(args.input_json).resolve()
  db_path = Path(args.output_db).resolve()

  data = load_json(json_path)

  conn = open_db(db_path)
  try:
    with conn:
      if args.mode == "rebuild":
        rebuild_schema(conn)
      else:
        ensure_schema(conn)

      # 先用 DB 參照做驗證，支援「JSON 只帶新增內容」
      validate_dataset(conn, data)

      # 寫入（缺少的區塊視為空）
      upsert_meta(conn, data.get("meta", {}) or {})
      upsert_unit_conversions(conn, data.get("unit_conversions", []) or [])
      upsert_ingredients(conn, data.get("ingredients", []) or [])
      upsert_dishes_and_links(conn, data.get("dishes", []) or [], sync_dish_links=args.sync_dish_links)
      upsert_prices(conn, data.get("prices", []) or [])
      upsert_inventory(conn, data.get("inventory", []) or [])

      # 可選：記錄匯入時間（不影響主資料）
      upsert_meta(conn, {"last_import_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

    print(f"✅ 匯入完成：{db_path}")

    # 小檢查
    cur = conn.cursor()
    cur.execute("SELECT role, COUNT(*) FROM dishes GROUP BY role ORDER BY role")
    print("— dishes by role —")
    for r, c in cur.fetchall():
      print(f"{r}: {c}")

    cur.execute("SELECT COUNT(*) FROM dish_ingredients")
    print(f"— dish_ingredients rows — {cur.fetchone()[0]}")

  finally:
    conn.close()


if __name__ == "__main__":
  main()
