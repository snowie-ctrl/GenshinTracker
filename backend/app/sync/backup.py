import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import BACKUPS_KEPT


def backup_db(db_file: Path, backups_dir: Path, now: datetime, keep: int = BACKUPS_KEPT) -> Path | None:
    """Consistent copy via SQLite's backup API; keep only the newest `keep` copies."""
    if not db_file.exists():
        return None
    backups_dir.mkdir(parents=True, exist_ok=True)
    dest = backups_dir / f"tracker-{now:%Y%m%d-%H%M%S-%f}.db"
    src = sqlite3.connect(db_file)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    for old in sorted(backups_dir.glob("tracker-*.db"))[:-keep]:
        old.unlink()
    return dest
