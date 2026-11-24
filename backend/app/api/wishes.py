# backend/app/api/wishes.py
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select

from app.config import APP_VERSION, WISH_HISTORY_PAGE_SIZE, WISH_UPLOAD_MAX_BYTES
from app.context import AppContext, get_ctx
from app.db.models import GameBanner, GameCharacter, GameWeapon, Wish, WishChart
from app.servertime import offset_hours
from app.settings.envfile import read_env
from app.timeutil import iso, utcnow
from app.wishes.importer import ImportBusy
from app.wishes.analysis import analyze, load_items, load_phases
from app.wishes.pity import PoolResult, PullView, banner_windows, summarize
from app.wishes.stats import banner_timeline, overall_stats, pool_stats
from app.wishes.types import NEEDS_UID, POOLS
from app.wishes.uigf import build_uigf

router = APIRouter()
BUSY = "Another import is running."


class ChartIn(BaseModel):
    item_id: int | None


def _env(ctx: AppContext) -> dict:
    return read_env(ctx.paths.env_file)


def _offset(ctx: AppContext) -> int:
    return offset_hours(_env(ctx).get("GENSHIN_REGION"))


def _icons(session) -> dict[int, str]:
    icons = {i: icon for i, icon in session.execute(select(GameWeapon.id, GameWeapon.icon))}
    icons.update({i: icon for i, icon in session.execute(select(GameCharacter.id, GameCharacter.icon))})
    return icons


def _pull(p: PullView, icons: dict[int, str]) -> dict:
    return {"name": p.name, "item_id": p.item_id, "icon": icons.get(p.item_id), "item_type": p.item_type,
            "rarity": p.rarity, "time": p.time, "pity": p.pity, "outcome": p.outcome, "banner": p.banner}


def pool_payload(r: PoolResult, icons: dict[int, str]) -> dict:
    return {"pool": r.pool, "total": r.total, "pity5": r.pity5, "pity4": r.pity4, "hard": r.hard, "soft": r.soft,
            "in_soft": r.in_soft, "next_state": r.next_state, "fate": r.fate, "radiance": r.radiance,
            "stats": pool_stats(r), "avg_pity": pool_stats(r)["avg_five_pity"], "fives": [_pull(p, icons) for p in reversed(r.fives)],
            "fours": [_pull(p, icons) for p in reversed(r.fours)]}


def pity_lines(results: dict[str, PoolResult]) -> list[dict]:
    return [{"pool": p, "pity5": results[p].pity5, "hard": results[p].hard, "next_state": results[p].next_state,
             "fate_points": (results[p].fate or {}).get("points")} for p in POOLS if results[p].total]


@router.post("/wishes/import/game")
async def import_game(ctx: AppContext = Depends(get_ctx)) -> dict:
    try:
        return {"import_id": await ctx.wishes.start_game()}
    except ImportBusy:
        raise HTTPException(409, BUSY) from None


@router.post("/wishes/import/file")
async def import_file(file: UploadFile, ctx: AppContext = Depends(get_ctx)) -> dict:
    name = file.filename or ""
    if not name.lower().endswith((".json", ".xlsx")):
        raise HTTPException(400, "Upload a UIGF .json file, a paimon.moe data backup (.json) or a paimon.moe .xlsx export.")
    content = await file.read(WISH_UPLOAD_MAX_BYTES + 1)
    if len(content) > WISH_UPLOAD_MAX_BYTES:
        raise HTTPException(413, "The file is larger than 20 MB.")
    try:
        return await ctx.wishes.import_file(name, content)
    except ImportBusy:
        raise HTTPException(409, BUSY) from None


@router.get("/wishes/import/status")
def import_status(ctx: AppContext = Depends(get_ctx)) -> dict:
    return ctx.wishes.status()


@router.get("/wishes/summary")
def summary(ctx: AppContext = Depends(get_ctx)) -> dict:
    offset = _offset(ctx)
    with ctx.session_factory() as s:
        results = summarize(s, utcnow(), offset)
        icons = _icons(s)
        rows = list(s.scalars(select(Wish)))
        game_banners = list(s.scalars(select(GameBanner)))
        items = load_items(s)
    phases = load_phases(banner_windows(game_banners, offset).get("character", []))
    return {
        "pools": [pool_payload(results[p], icons) for p in POOLS if results[p].total],
        "overall": overall_stats(results),
        "analysis": analyze(results, rows, phases, items),
        "banners": banner_timeline(results),
        "banners_available": bool(game_banners),
        "import": ctx.wishes.status(),
    }


@router.get("/wishes")
def history(pool: str | None = None, rarity: int | None = None,
            type: Literal["character", "weapon"] | None = None, banner: str | None = None,
            q: str | None = None, page: int = Query(1, ge=1), ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        results = summarize(s, utcnow(), _offset(ctx))
        icons = _icons(s)
        rows = list(s.scalars(select(Wish).order_by(Wish.time.desc(), Wish.seq.desc(), Wish.pk.desc())))
    pity_at = {pk: v for r in results.values() for pk, v in r.pity_at.items()}
    banner_at = {pk: v for r in results.values() for pk, v in r.banner_at.items()}
    needle = (q or "").strip().casefold()

    def keep(w: Wish) -> bool:
        b = banner_at.get(w.pk)
        return ((pool is None or w.pool == pool) and (rarity is None or w.rarity == rarity)
                and (type is None or w.item_type == type) and (banner is None or (b is not None and b.key == banner))
                and (not needle or needle in w.name.casefold()))

    filtered = [w for w in rows if keep(w)]
    size = WISH_HISTORY_PAGE_SIZE
    chunk = filtered[(page - 1) * size: page * size]
    return {"total": len(filtered), "page": page, "page_size": size, "rows": [
        {"time": w.time, "name": w.name, "item_id": w.item_id, "icon": icons.get(w.item_id),
         "item_type": w.item_type, "rarity": w.rarity, "pool": w.pool,
         "banner": banner_at[w.pk].short_name if banner_at.get(w.pk) else None,
         "banner_key": banner_at[w.pk].key if banner_at.get(w.pk) else None,
         "pity": pity_at.get(w.pk)} for w in chunk]}


@router.put("/wishes/chart/{pool}")
def set_chart(pool: str, body: ChartIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    if pool not in ("weapon", "chronicled"):
        raise HTTPException(404, "Only the Weapon and Chronicled banners have a chart.")
    offset = _offset(ctx)
    with ctx.session_factory.begin() as s:
        if body.item_id is None:
            row = s.get(WishChart, pool)
            if row is not None:
                s.delete(row)
        else:
            fate = summarize(s, utcnow(), offset)[pool].fate or {}
            if body.item_id not in {c["item_id"] for c in fate.get("choices", [])}:
                raise HTTPException(400, "Pick one of the current banner's featured 5★ items.")
            s.merge(WishChart(pool=pool, item_id=body.item_id, set_at=utcnow()))
    with ctx.session_factory() as s:
        return pool_payload(summarize(s, utcnow(), offset)[pool], _icons(s))


@router.get("/wishes/export")
def export(ctx: AppContext = Depends(get_ctx)) -> JSONResponse:
    env = _env(ctx)
    if not env.get("GENSHIN_UID"):
        raise HTTPException(400, NEEDS_UID)
    now = utcnow()
    with ctx.session_factory() as s:
        rows = list(s.scalars(select(Wish)))
    data = build_uigf(rows, int(env["GENSHIN_UID"]), offset_hours(env.get("GENSHIN_REGION")), now, APP_VERSION)
    filename = f"ad-astra-uigf-{now:%Y-%m-%d}.json"
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/wishes/cache-status")
def cache_status(ctx: AppContext = Depends(get_ctx)) -> dict:
    st = ctx.wishes.cache_status()
    return {"status": st["status"], "cached_at": iso(st["cached_at"])}
