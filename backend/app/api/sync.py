from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.context import AppContext, get_ctx
from app.db.models import SyncRun
from app.sync.runner import SyncTooSoon
from app.timeutil import iso

router = APIRouter()


def run_dict(run: SyncRun) -> dict:
    return {
        "id": run.id, "trigger": run.trigger, "started_at": iso(run.started_at),
        "finished_at": iso(run.finished_at), "parts": run.parts,
    }


@router.post("/sync")
async def start_sync(trigger: Literal["auto", "manual"] = "auto", ctx: AppContext = Depends(get_ctx)) -> dict:
    try:
        result = await ctx.sync.request(trigger)
    except SyncTooSoon as e:
        raise HTTPException(429, f"Wait {e.retry_after}s before syncing again.",
                            headers={"Retry-After": str(e.retry_after)}) from None
    return {"run_id": result.run_id, "started": result.started, "reason": result.reason}


@router.get("/sync/status")
def sync_status(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        runs = s.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(10)).all()
        return {"running": ctx.sync.running, "runs": [run_dict(r) for r in runs]}
