from sqlalchemy.orm import Session

from app.db.models import GapRun
from app.planner.requests import snapshot
from app.timeutil import iso


def gap_status(session: Session, pending: bool, connected: bool) -> dict:
    """`stale` means "a recalculation is coming": only possible while connected."""
    run = session.get(GapRun, 1)
    current = snapshot(session)
    if run is None:
        return {"computed_at": None, "ok": None, "error": None, "skipped": [],
                "stale": connected and (pending or bool(current))}
    return {
        "computed_at": iso(run.computed_at), "ok": run.ok, "error": run.error, "skipped": run.skipped or [],
        "stale": connected and (pending or run.snapshot != current),
    }
