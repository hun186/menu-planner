import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple


DDL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS unit_conversions;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS ingredient_prices;
DROP TABLE IF EXISTS dish_ingredients;
DROP TABLE IF EXISTS dishes;
DROP TABLE IF EXISTS ingredients;
DROP TABLE IF EXISTS meta;

CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE ingredients (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  protein_group TEXT,
  default_unit TEXT NOT NULL
);

CREATE TABLE dishes (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('main','side','soup','fruit')),
  cuisine TEXT,
  meat_type TEXT,
  tags_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE dish_ingredients (
  dish_id TEXT NOT NULL,
  ingredient_id TEXT NOT NULL,
  qty REAL NOT NULL,
  unit TEXT NOT NULL,
  PRIMARY KEY (dish_id, ingredient_id),
  FOREIGN KEY (dish_id) REFERENCES dishes(id) ON DELETE CASCADE,
  FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE RESTRICT
);

CREATE TABLE ingredient_prices (
  ingredient_id TEXT NOT NULL,
  price_date TEXT NOT NULL,               -- YYYY-MM-DD
  price_per_unit REAL NOT NULL,
  unit TEXT NOT NULL,
  PRIMARY KEY (ingredient_id, price_date),
  FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
);

CREATE TABLE inventory (
  ingredient_id TEXT PRIMARY KEY,
  qty_on_hand REAL NOT NULL,
  unit TEXT NOT NULL,
  updated_at TEXT NOT NULL,               -- YYYY-MM-DD
  expiry_date TEXT,                       -- YYYY-MM-DD (nullable)
  FOREIGN KEY (ingredient_id) REFERENCES ingredients(id) ON DELETE CASCADE
);

CREATE TABLE unit_conversions (
  from_unit TEXT NOT NULL,
  to_unit TEXT NOT NULL,
  factor REAL NOT NULL,
  PRIMARY KEY (from_unit, to_unit)
);

-- Indexes for faster query
CREATE INDEX idx_dishes_role ON dishes(role);
CREATE INDEX idx_dishes_meat_type ON dishes(meat_type);
CREATE INDEX idx_di_ingredient ON dish_ingredients(ingredient_id);
CREATE INDEX idx_prices_date ON ingredient_prices(price_date);
"""


def _as_text(v: Any) -> str:
  if v is None:
    return ""
  if isinstance(v, (dict, list)):
    return json.dumps(v, ensure_ascii=False)
  return str(v)


def validate_dataset(data: Dict[str, Any]) -> None:
  # Basic structure checks
  for k in ["meta", "ingredients", "dishes", "prices", "inventory", "unit_conversions"]:
    if k not in data:
      raise ValueError(f"JSON 缺少必要欄位：{k}")

  ing_ids = set()
  for ing in data["ingredients"]:
    if ing["id"] in ing_ids:
      raise ValueError(f"ingredients.id 重複：{ing['id']}")
    ing_ids.add(ing["id"])

  dish_ids = set()
  for dish in data["dishes"]:
    if dish["id"] in dish_ids:
      raise ValueError(f"dishes.id 重複：{dish['id']}")
    dish_ids.add(dish["id"])
    # Ingredient reference check
    for di in dish.get("ingredients", []):
      if di["ingredient_id"] not in ing_ids:
        raise ValueError(f"菜色 {dish['id']} 引用不存在食材：{di['ingredient_id']}")

  for inv in data["inventory"]:
    if inv["ingredient_id"] not in ing_ids:
      raise ValueError(f"inventory 引用不存在食材：{inv['ingredient_id']}")

  for p in data["prices"]:
    if p["ingredient_id"] not in ing_ids:
      raise ValueError(f"prices 引用不存在食材：{p['ingredient_id']}")


def load_json(path: Path) -> Dict[str, Any]:
  with path.open("r", encoding="utf-8") as f:
    return json.load(f)


def create_db(db_path: Path) -> sqlite3.Connection:
  conn = sqlite3.connect(str(db_path))
  conn.execute("PRAGMA foreign_keys = ON;")
  conn.executescript(DDL)
  return conn


def insert_meta(conn: sqlite3.Connection, meta: Dict[str, Any]) -> None:
  rows = [(k, _as_text(v)) for k, v in meta.items()]
  conn.executemany("INSERT INTO meta(key, value) VALUES (?, ?)", rows)


def insert_unit_conversions(conn: sqlite3.Connection, convs: List[Dict[str, Any]]) -> None:
  rows = [(c["from_unit"], c["to_unit"], float(c["factor"])) for c in convs]
  conn.executemany(
    "INSERT INTO unit_conversions(from_unit, to_unit, factor) VALUES (?, ?, ?)",
    rows
  )


def insert_ingredients(conn: sqlite3.Connection, ingredients: List[Dict[str, Any]]) -> None:
  rows = []
  for ing in ingredients:
    rows.append((
      ing["id"],
      ing["name"],
      ing["category"],
      ing.get("protein_group"),
      ing["default_unit"]
    ))
  conn.executemany(
    "INSERT INTO ingredients(id, name, category, protein_group, default_unit) VALUES (?, ?, ?, ?, ?)",
    rows
  )


def insert_dishes_and_links(conn: sqlite3.Connection, dishes: List[Dict[str, Any]]) -> None:
  dish_rows = []
  link_rows = []

  for d in dishes:
    dish_rows.append((
      d["id"],
      d["name"],
      d["role"],
      d.get("cuisine"),
      d.get("meat_type"),
      json.dumps(d.get("tags", []), ensure_ascii=False)
    ))
    for di in d.get("ingredients", []):
      link_rows.append((
        d["id"],
        di["ingredient_id"],
        float(di["qty"]),
        di["unit"]
      ))

  conn.executemany(
    "INSERT INTO dishes(id, name, role, cuisine, meat_type, tags_json) VALUES (?, ?, ?, ?, ?, ?)",
    dish_rows
  )
  conn.executemany(
    "INSERT INTO dish_ingredients(dish_id, ingredient_id, qty, unit) VALUES (?, ?, ?, ?)",
    link_rows
  )


def insert_prices(conn: sqlite3.Connection, prices: List[Dict[str, Any]]) -> None:
  rows = []
  for p in prices:
    rows.append((
      p["ingredient_id"],
      p["price_date"],
      float(p["price_per_unit"]),
      p["unit"]
    ))
  conn.executemany(
    "INSERT INTO ingredient_prices(ingredient_id, price_date, price_per_unit, unit) VALUES (?, ?, ?, ?)",
    rows
  )


def insert_inventory(conn: sqlite3.Connection, inv_list: List[Dict[str, Any]]) -> None:
  rows = []
  for inv in inv_list:
    rows.append((
      inv["ingredient_id"],
      float(inv["qty_on_hand"]),
      inv["unit"],
      inv["updated_at"],
      inv.get("expiry_date")
    ))
  conn.executemany(
    "INSERT INTO inventory(ingredient_id, qty_on_hand, unit, updated_at, expiry_date) VALUES (?, ?, ?, ?, ?)",
    rows
  )


def main():
  if len(sys.argv) < 3:
    print("用法：python json_to_sqlite.py <input.json> <output.db>")
    sys.exit(1)

  json_path = Path(sys.argv[1]).resolve()
  db_path = Path(sys.argv[2]).resolve()

  data = load_json(json_path)
  validate_dataset(data)

  conn = create_db(db_path)
  try:
    with conn:
      insert_meta(conn, data.get("meta", {}))
      insert_unit_conversions(conn, data.get("unit_conversions", []))
      insert_ingredients(conn, data.get("ingredients", []))
      insert_dishes_and_links(conn, data.get("dishes", []))
      insert_prices(conn, data.get("prices", []))
      insert_inventory(conn, data.get("inventory", []))

    print(f"✅ 匯入完成：{db_path}")
    # Small sanity checks
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
