import asyncio
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import GAMEDATA_MAX_AGE_DAYS
from app.db.models import GameBanner, GameCharacter, GameDomain, GameMaterial, GameMeta, GameWeapon
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


META_BANNERS_FETCHED = "banners_fetched_at"
META_BANNERS_ERROR = "banners_last_error"
META_BANNERS_UNMAPPED = "banners_unmapped"


def banners_need_refresh(session: Session, now: datetime) -> bool:
    fetched = _get_meta(session, META_BANNERS_FETCHED)
    if not fetched or session.scalar(select(func.count()).select_from(GameBanner)) == 0:
        return True
    return now - datetime.fromisoformat(fetched.rstrip("Z")) > timedelta(days=GAMEDATA_MAX_AGE_DAYS)


async def refresh_banners(session_factory: sessionmaker, http: httpx.AsyncClient,
                          now: datetime | None = None, force: bool = False) -> bool:
    """Download paimon.moe's banner list if stale (or forced). Needs characters and weapons first."""
    from app.wishes.banners import BannerParseError, build_banners, fetch_banners_js, parse_banners, slug_index
    now = now or utcnow()
    with session_factory() as s:
        if not force and not banners_need_refresh(s, now):
            return False
    with session_factory() as s:
        slugs = slug_index(s)
    try:
        banners, unmapped = build_banners(parse_banners(await fetch_banners_js(http)), slugs)
    except (*FETCH_ERRORS, BannerParseError) as e:
        message = f"{type(e).__name__}: {e}"[:300]
        log.warning("Banner data refresh failed: %s", message)
        with session_factory.begin() as s:
            _set_meta(s, META_BANNERS_ERROR, message)
        return False
    with session_factory.begin() as s:
        s.execute(delete(GameBanner))
        for b in banners:
            s.add(GameBanner(key=b.key, pool=b.pool, name=b.name, short_name=b.short_name, start=b.start,
                             end=b.end, timezone_dependent=b.timezone_dependent,
                             timezone_dependent_end=b.timezone_dependent_end, order=b.order,
                             featured_5=b.featured_5, featured_4=b.featured_4, version=b.version))
        _set_meta(s, META_BANNERS_FETCHED, iso(now))
        _set_meta(s, META_BANNERS_ERROR, None)
        _set_meta(s, META_BANNERS_UNMAPPED, sorted(unmapped))
    return True


async def refresh_all(session_factory: sessionmaker, http: httpx.AsyncClient,
                      now: datetime | None = None, force: bool = False) -> bool:
    characters = await refresh(session_factory, http, now=now, force=force)
    materials = await refresh_materials(session_factory, http, now=now, force=force)
    banners = await refresh_banners(session_factory, http, now=now, force=force or characters or materials)
    return characters or materials or banners


META_UNKNOWN_REFRESH = "unknown_ids_refresh"
UNKNOWN_REFRESH_EVERY = timedelta(hours=1)


def claim_unknown_ids_refresh(session: Session, ids: set[int], now: datetime) -> bool:
    """True (and remembered) unless this same set of unknown material ids already forced a
    refresh within the last hour; a gaps run every few edits must not re-download everything."""
    key = sorted(ids)
    last = _get_meta(session, META_UNKNOWN_REFRESH)
    if (last and last.get("ids") == key
            and now - datetime.fromisoformat(last["at"].rstrip("Z")) < UNKNOWN_REFRESH_EVERY):
        return False
    _set_meta(session, META_UNKNOWN_REFRESH, {"ids": key, "at": iso(now)})
    return True


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
        "banners": {
            "fetched_at": _get_meta(session, META_BANNERS_FETCHED),
            "last_error": _get_meta(session, META_BANNERS_ERROR),
            "count": session.scalar(select(func.count()).select_from(GameBanner)) or 0,
            "unmapped": _get_meta(session, META_BANNERS_UNMAPPED) or [],
        },
    }
