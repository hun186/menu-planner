from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import shutil
from typing import Dict, List

DAILY_BACKUP_LIMIT = 50
BACKUP_REASON_DEFAULT = "admin_modify_before_change"


def create_db_backup(
    db_path: str,
    keep_latest_per_day: int = DAILY_BACKUP_LIMIT,
    reason: str = BACKUP_REASON_DEFAULT,
    comment: str = "",
) -> Path:
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
    upsert_backup_metadata(
        db_path=db_path,
        backup_filename=dst.name,
        reason=reason,
        comment=comment,
    )

    removed = _prune_daily_backups(
        backup_dir=backup_dir,
        db_stem=src.stem,
        db_suffix=src.suffix or ".db",
        day_key=day_key,
        keep_latest=keep_latest_per_day,
    )
    if removed:
        payload = _read_backup_metadata(backup_dir, src.stem)
        dirty = False
        for p in removed:
            if payload.pop(p.name, None) is not None:
                dirty = True
        if dirty:
            _write_backup_metadata(backup_dir, src.stem, payload)

    return dst


def _metadata_file(backup_dir: Path, db_stem: str) -> Path:
    return backup_dir / f"{db_stem}_backup_meta.json"


def _read_backup_metadata(backup_dir: Path, db_stem: str) -> Dict[str, dict]:
    path = _metadata_file(backup_dir, db_stem)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}
    normalized: Dict[str, dict] = {}
    for name, meta in payload.items():
        if isinstance(name, str) and isinstance(meta, dict):
            normalized[name] = meta
    return normalized


def _write_backup_metadata(backup_dir: Path, db_stem: str, payload: Dict[str, dict]) -> None:
    path = _metadata_file(backup_dir, db_stem)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def upsert_backup_metadata(
    *,
    db_path: str,
    backup_filename: str,
    reason: str = BACKUP_REASON_DEFAULT,
    comment: str = "",
) -> None:
    db_file = Path(db_path).resolve()
    backup_dir = db_file.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    payload = _read_backup_metadata(backup_dir, db_file.stem)
    payload[backup_filename] = {
        "reason": str(reason or BACKUP_REASON_DEFAULT).strip(),
        "comment": str(comment or "").strip(),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    _write_backup_metadata(backup_dir, db_file.stem, payload)


def get_backup_metadata_map(db_path: str) -> Dict[str, dict]:
    db_file = Path(db_path).resolve()
    backup_dir = db_file.parent / "backups"
    if not backup_dir.exists():
        return {}
    return _read_backup_metadata(backup_dir, db_file.stem)


def remove_backup_metadata(db_path: str, backup_filename: str) -> None:
    db_file = Path(db_path).resolve()
    backup_dir = db_file.parent / "backups"
    if not backup_dir.exists():
        return
    payload = _read_backup_metadata(backup_dir, db_file.stem)
    if backup_filename in payload:
        payload.pop(backup_filename, None)
        _write_backup_metadata(backup_dir, db_file.stem, payload)


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
