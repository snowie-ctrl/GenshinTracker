from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now — the only form stored in SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.replace(microsecond=0).isoformat() + "Z"
