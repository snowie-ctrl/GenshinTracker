from sqlalchemy.orm import Session

from app.db.models import GapRun
from app.planner.requests import snapshot
from app.timeutil import iso


def gap_status(session: Session, pending: bool, connected: bool) -> dict:
    """`stale` means "a recalculation is coming"; `pending` means one is scheduled or running right now
    (it wins over a previous failure). Both are only possible while connected."""
    pending = connected and pending
    run = session.get(GapRun, 1)
    current = snapshot(session)
    if run is None:
        return {"computed_at": None, "ok": None, "error": None, "skipped": [], "pending": pending,
                "stale": connected and (pending or bool(current))}
    return {
        "computed_at": iso(run.computed_at), "ok": run.ok, "error": run.error, "skipped": run.skipped or [],
        "pending": pending, "stale": connected and (pending or run.snapshot != current),
    }
