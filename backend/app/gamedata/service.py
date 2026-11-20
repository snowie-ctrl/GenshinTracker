import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import GAMEDATA_MAX_AGE_DAYS
from app.db.models import GameCharacter, GameDomain, GameMaterial, GameMeta, GameWeapon
from app.gamedata.materials import (CATEGORIES, fetch_daily_dungeon, fetch_material_detail,
                                    fetch_material_list, fetch_weapon_list)
from app.gamedata.yatta import CharacterData, fetch_avatar_list
from app.timeutil import iso, utcnow

log = logging.getLogger(__name__)
META_FETCHED = "characters_fetched_at"
META_ERROR = "characters_last_error"


def _get_meta(session: Session, key: str):
    row = session.get(GameMeta, key)
    return row.value if row else None


def _set_meta(session: Session, key: str, value) -> None:
    session.merge(GameMeta(key=key, value=value))


def needs_refresh(session: Session, now: datetime) -> bool:
    fetched = _get_meta(session, META_FETCHED)
    if not fetched or session.scalar(select(func.count()).select_from(GameCharacter)) == 0:
        return True
    return now - datetime.fromisoformat(fetched.rstrip("Z")) > timedelta(days=GAMEDATA_MAX_AGE_DAYS)


def _store(session: Session, chars: list[CharacterData], now: datetime) -> None:
    for c in chars:
        session.merge(GameCharacter(
            id=c.id, name=c.name, slug=c.slug, rarity=c.rarity, element=c.element,
            weapon_type=c.weapon_type, region=c.region, icon=c.icon, splash=c.splash,
            release_at=c.release_at,
        ))
    _set_meta(session, META_FETCHED, iso(now))
    _set_meta(session, META_ERROR, None)


async def refresh(session_factory: sessionmaker, http: httpx.AsyncClient,
                  now: datetime | None = None, force: bool = False) -> bool:
    """Download the character list if stale (or forced). Returns True if data was stored."""
    now = now or utcnow()
    with session_factory() as s:
        if not force and not needs_refresh(s, now):
            return False
    try:
        chars = await fetch_avatar_list(http)
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
        message = f"{type(e).__name__}: {e}"[:300]
        log.warning("Game data refresh failed: %s", message)
        with session_factory.begin() as s:
            _set_meta(s, META_ERROR, message)
        return False
    with session_factory.begin() as s:
        _store(s, chars, now)
    return True


META_MAT_FETCHED = "materials_fetched_at"
META_MAT_ERROR = "materials_last_error"
DETAIL_CONCURRENCY = 4
FETCH_ERRORS = (httpx.HTTPError, KeyError, ValueError, TypeError)


def materials_need_refresh(session: Session, now: datetime) -> bool:
    fetched = _get_meta(session, META_MAT_FETCHED)
    if not fetched or session.scalar(select(func.count()).select_from(GameMaterial)) == 0:
        return True
    if session.scalar(select(func.count()).select_from(GameMaterial).where(GameMaterial.detail_fetched.is_(False))):
        return True
    return now - datetime.fromisoformat(fetched.rstrip("Z")) > timedelta(days=GAMEDATA_MAX_AGE_DAYS)


def _store_catalogue(session: Session, mats, weapons, domains) -> list[tuple[int, int]]:
    """Upsert list data; keep details already fetched. Returns (id, rarity) still needing details."""
    for m in mats:
        row = session.get(GameMaterial, m.id)
        region = [{"kind": "region", "name": m.region, "days": []}] if m.region else []
        if row is None:
            row = GameMaterial(id=m.id, sources=region, detail_fetched=False, sort_order=0)
            session.add(row)
        row.name, row.icon, row.rarity = m.name, m.icon, m.rarity
        row.yatta_type, row.category = m.yatta_type, m.category
    for w in weapons:
        session.merge(GameWeapon(id=w.id, name=w.name, icon=w.icon, rarity=w.rarity, weapon_type=w.weapon_type))
    session.execute(delete(GameDomain))
    for d in domains:
        session.add(GameDomain(id=d.id, name=d.name, kind=d.kind, city=d.city, weekdays=d.weekdays,
                               material_ids=d.material_ids))
    session.flush()
    return [(r.id, r.rarity) for r in session.scalars(select(GameMaterial).where(GameMaterial.detail_fetched.is_(False)))]


def _recompute_family_and_order(session: Session) -> None:
    rows = list(session.scalars(select(GameMaterial)))
    by_id = {r.id: r for r in rows}
    for r in rows:
        root, steps = r, 0
        while root.craft_from in by_id and steps < 10:
            root, steps = by_id[root.craft_from], steps + 1
        r.family = root.id
    ordered = sorted(rows, key=lambda r: (CATEGORIES.index(r.category), r.yatta_type, r.family, r.rarity, r.id))
    for i, r in enumerate(ordered):
        r.sort_order = i


async def refresh_materials(session_factory: sessionmaker, http: httpx.AsyncClient,
                            now: datetime | None = None, force: bool = False) -> bool:
    """Download material/weapon/domain data if stale (or forced). Returns True if data was stored."""
    now = now or utcnow()
    with session_factory() as s:
        if not force and not materials_need_refresh(s, now):
            return False
    try:
        mats = await fetch_material_list(http)
        weapons = await fetch_weapon_list(http)
        domains = await fetch_daily_dungeon(http, {m.id for m in mats if m.category in ("talent", "weapon")})
    except FETCH_ERRORS as e:
        message = f"{type(e).__name__}: {e}"[:300]
        log.warning("Material data refresh failed: %s", message)
        with session_factory.begin() as s:
            _set_meta(s, META_MAT_ERROR, message)
        return False
    with session_factory.begin() as s:
        todo = _store_catalogue(s, mats, weapons, domains)

    sem = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async def one(mid: int, rarity: int):
        async with sem:
            try:
                return mid, await fetch_material_detail(http, mid, rarity)
            except FETCH_ERRORS:
                return mid, None

    results = await asyncio.gather(*(one(mid, rarity) for mid, rarity in todo))
    failures = 0
    with session_factory.begin() as s:
        for mid, detail in results:
            if detail is None:
                failures += 1
                continue
            row = s.get(GameMaterial, mid)
            row.craft_from = detail.craft_from
            row.sources = [x for x in row.sources if x["kind"] == "region"] + detail.sources
            row.detail_fetched = True
        _recompute_family_and_order(s)
        _set_meta(s, META_MAT_FETCHED, iso(now))
        _set_meta(s, META_MAT_ERROR,
                  f"{failures} material detail(s) failed; retried on next refresh" if failures else None)
    return True


async def refresh_all(session_factory: sessionmaker, http: httpx.AsyncClient,
                      now: datetime | None = None, force: bool = False) -> bool:
    characters = await refresh(session_factory, http, now=now, force=force)
    materials = await refresh_materials(session_factory, http, now=now, force=force)
    return characters or materials


def gamedata_status(session: Session) -> dict:
    return {
        "fetched_at": _get_meta(session, META_FETCHED),
        "last_error": _get_meta(session, META_ERROR),
        "count": session.scalar(select(func.count()).select_from(GameCharacter)) or 0,
        "materials": {
            "fetched_at": _get_meta(session, META_MAT_FETCHED),
            "last_error": _get_meta(session, META_MAT_ERROR),
            "count": session.scalar(select(func.count()).select_from(GameMaterial)) or 0,
        },
    }
