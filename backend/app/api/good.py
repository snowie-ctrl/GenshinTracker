"""GOOD (scanner export) import. Opt-in via the good_import_enabled setting; the file is parsed in memory only."""
import re

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import GOOD_UPLOAD_MAX_BYTES
from app.context import AppContext, get_ctx
from app.db.models import GameArtifactSet, GameCharacter, GameMaterial, GameWeapon, GoodArtifactRow, GoodImport, GoodWeaponRow
from app.good.keys import KeyIndex
from app.good.parse import SLOTS, GoodFormatError, parse_good
from app.good.store import delete_snapshot, good_active, good_enabled, import_summary, replace_snapshot
from app.timeutil import utcnow

router = APIRouter()
NOT_ENABLED = "Turn on GOOD inventory import in Settings first."
SLOT_ICON = {"flower": 4, "plume": 2, "sands": 5, "goblet": 1, "circlet": 3}


def holders(session: Session, ids: set[int]) -> dict[int, dict]:
    if not ids:
        return {}
    rows = session.scalars(select(GameCharacter).where(GameCharacter.id.in_(ids)))
    return {c.id: {"id": c.id, "name": c.name, "slug": c.slug, "icon": c.icon} for c in rows}


def _require_active(session: Session) -> None:
    if good_active(session) is None:
        raise HTTPException(404, "No GOOD import")


@router.get("/good/status")
def status(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        row = s.get(GoodImport, 1)
        base = {"enabled": good_enabled(s), "imported_at": None, "source": None, "counts": None, "unmatched": []}
        return base | ({k: v for k, v in import_summary(row).to_dict().items()} if row else {})


@router.post("/good/import")
async def import_good(file: UploadFile, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        if not good_enabled(s):
            raise HTTPException(409, NOT_ENABLED)
    content = await file.read(GOOD_UPLOAD_MAX_BYTES + 1)
    if len(content) > GOOD_UPLOAD_MAX_BYTES:
        raise HTTPException(413, "The file is larger than 20 MB.")
    try:
        parsed = parse_good(content)
    except GoodFormatError as e:
        raise HTTPException(400, str(e)) from None
    with ctx.session_factory.begin() as s:
        if not s.scalar(select(func.count()).select_from(GameMaterial)):
            raise HTTPException(409, "Refresh game data first")
        return replace_snapshot(s, parsed, KeyIndex.build(s), utcnow()).to_dict()


@router.delete("/good", status_code=204)
def delete_good(ctx: AppContext = Depends(get_ctx)) -> Response:
    with ctx.session_factory.begin() as s:
        delete_snapshot(s)
    return Response(status_code=204)


@router.get("/good/weapons")
def good_weapons(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        _require_active(s)
        rows = s.execute(select(GoodWeaponRow, GameWeapon).join(GameWeapon, GameWeapon.id == GoodWeaponRow.weapon_id)).all()
        who = holders(s, {w.character_id for w, _ in rows if w.character_id})
        out = [{"id": w.id, "weapon_id": w.weapon_id, "name": g.name, "icon": g.icon, "rarity": g.rarity,
                "weapon_type": g.weapon_type, "level": w.level, "ascension": w.ascension,
                "refinement": w.refinement, "lock": w.lock, "location": w.location,
                "holder": who.get(w.character_id)} for w, g in rows]
        return sorted(out, key=lambda x: (-x["rarity"], x["name"], -x["level"], x["id"]))


@router.get("/good/artifacts")
def good_artifacts(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        _require_active(s)
        rows = s.execute(select(GoodArtifactRow, GameArtifactSet)
                         .join(GameArtifactSet, GameArtifactSet.id == GoodArtifactRow.set_id)).all()
        who = holders(s, {a.character_id for a, _ in rows if a.character_id})
        out = [{"id": a.id, "set_id": a.set_id, "set_name": g.name,
                "icon": re.sub(r"_\d+$", f"_{SLOT_ICON[a.slot]}", g.icon), "slot": a.slot, "rarity": a.rarity,
                "level": a.level, "main_stat": a.main_stat, "substats": a.substats, "lock": a.lock,
                "location": a.location, "holder": who.get(a.character_id)} for a, g in rows]
        return sorted(out, key=lambda x: (-x["rarity"], x["set_name"], SLOTS.index(x["slot"]), -x["level"], x["id"]))
