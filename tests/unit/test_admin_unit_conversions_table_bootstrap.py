import sqlite3

from src.menu_planner.db.admin_repo import SQLiteAdminRepo
from src.menu_planner.db.repo import SQLiteRepo


def _create_db_without_unit_conversions(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS ingredients (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          category TEXT NOT NULL,
          protein_group TEXT,
          default_unit TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def test_admin_repo_bootstraps_unit_conversions_table(tmp_path):
    db_path = str(tmp_path / "menu_legacy.db")
    _create_db_without_unit_conversions(db_path)
    repo = SQLiteAdminRepo(db_path)

    assert repo.list_unit_conversions() == []

    repo.upsert_unit_conversion("kg", "g", 1000)
    rows = repo.list_unit_conversions()
    assert rows == [{"from_unit": "kg", "to_unit": "g", "factor": 1000.0}]


def test_runtime_repo_bootstraps_unit_conversions_table(tmp_path):
    db_path = str(tmp_path / "menu_legacy.db")
    _create_db_without_unit_conversions(db_path)
    repo = SQLiteRepo(db_path)

    assert repo.fetch_unit_conversions() == {}

