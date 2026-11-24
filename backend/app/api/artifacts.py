from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.context import AppContext, get_ctx
from app.db.models import GameArtifactDomain, GameArtifactSet

router = APIRouter()


@router.get("/artifact-sets")
def artifact_sets(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    """Every known set with the domain that drops it (source: "domain", "none" = bosses/Strongbox, or "unknown" when no domains are stored)."""
    with ctx.session_factory() as s:
        source: dict[int, dict] = {}
        for d in s.scalars(select(GameArtifactDomain).order_by(GameArtifactDomain.id)):
            for sid in d.set_ids:
                source.setdefault(sid, {"id": d.id, "name": d.name, "entrance": d.entrance, "region": d.region})
        known = bool(source) or s.scalar(select(GameArtifactDomain.id).limit(1)) is not None
        rows = [{"id": a.id, "name": a.name, "icon": a.icon, "domain": source.get(a.id),
                 "source": "domain" if a.id in source else ("none" if known else "unknown")}
                for a in s.scalars(select(GameArtifactSet))]
    return sorted(rows, key=lambda r: r["name"])
