from datetime import datetime
from pathlib import Path

from src.menu_planner.db import backup as backup_mod


class _FakeDateTime(datetime):
    _now = datetime(2026, 3, 16, 9, 30, 0, 0)

    @classmethod
    def now(cls):
        return cls._now


def test_create_db_backup_copies_file_and_prunes_same_day(monkeypatch, tmp_path):
    monkeypatch.setattr(backup_mod, "datetime", _FakeDateTime)

    db = tmp_path / "menu.db"
    db.write_text("seed", encoding="utf-8")

    created = []
    for i in range(12):
        _FakeDateTime._now = datetime(2026, 3, 16, 9, 30, 0, i)
        created.append(backup_mod.create_db_backup(str(db), keep_latest_per_day=10))

    backup_dir = tmp_path / "backups"
    files = sorted(backup_dir.glob("menu_20260316_*.db"))

    assert len(files) == 10
    assert files[0].name.endswith("000002.db")
    assert files[-1].name.endswith("000011.db")
    assert created[-1].exists()


def test_create_db_backup_keeps_previous_day_files(monkeypatch, tmp_path):
    monkeypatch.setattr(backup_mod, "datetime", _FakeDateTime)

    db = tmp_path / "menu.db"
    db.write_text("seed", encoding="utf-8")

    # previous day backup should not be pruned by today's retention
    yesterday = tmp_path / "backups" / "menu_20260315_235959_999999.db"
    yesterday.parent.mkdir(parents=True, exist_ok=True)
    yesterday.write_text("old", encoding="utf-8")

    for i in range(11):
        _FakeDateTime._now = datetime(2026, 3, 16, 10, 0, 0, i)
        backup_mod.create_db_backup(str(db), keep_latest_per_day=10)

    today_files = sorted((tmp_path / "backups").glob("menu_20260316_*.db"))

    assert yesterday.exists()
    assert len(today_files) == 10
