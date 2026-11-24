from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.context import AppContext, get_ctx
from app.db.models import GameArtifactDomain, GameArtifactSet

router = APIRouter()


@router.get("/artifact-sets")
def artifact_sets(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    """Every known set with the domain that drops it (None: bosses, Strongbox, or unknown)."""
    with ctx.session_factory() as s:
        source: dict[int, dict] = {}
        for d in s.scalars(select(GameArtifactDomain).order_by(GameArtifactDomain.id)):
            for sid in d.set_ids:
                source.setdefault(sid, {"id": d.id, "name": d.name, "entrance": d.entrance, "region": d.region})
        rows = [{"id": a.id, "name": a.name, "icon": a.icon, "domain": source.get(a.id)}
                for a in s.scalars(select(GameArtifactSet))]
    return sorted(rows, key=lambda r: r["name"])
