from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
from typing import List


def create_db_backup(db_path: str, keep_latest_per_day: int = 10) -> Path:
    """
    Copy sqlite db to sibling backups dir and keep only latest N backups for same day.

    Backup path format:
      <db_dir>/backups/<db_stem>_YYYYMMDD_HHMMSS_microseconds.db
    """
    src = Path(db_path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"database file not found: {src}")

    now = datetime.now()
    day_key = now.strftime("%Y%m%d")
    ts = now.strftime("%Y%m%d_%H%M%S_%f")

    backup_dir = src.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    dst = backup_dir / f"{src.stem}_{ts}{src.suffix or '.db'}"
    shutil.copy2(src, dst)

    _prune_daily_backups(
        backup_dir=backup_dir,
        db_stem=src.stem,
        db_suffix=src.suffix or ".db",
        day_key=day_key,
        keep_latest=keep_latest_per_day,
    )

    return dst


def _prune_daily_backups(
    *,
    backup_dir: Path,
    db_stem: str,
    db_suffix: str,
    day_key: str,
    keep_latest: int,
) -> List[Path]:
    pattern = f"{db_stem}_{day_key}_*{db_suffix}"
    backups = sorted(backup_dir.glob(pattern), key=lambda p: p.name)

    if keep_latest < 0:
        keep_latest = 0

    to_remove = backups[:-keep_latest] if keep_latest else backups
    for p in to_remove:
        p.unlink(missing_ok=True)

    return to_remove
