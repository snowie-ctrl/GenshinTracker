import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import GAMEDATA_MAX_AGE_DAYS
from app.db.models import GameCharacter, GameMeta
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


def gamedata_status(session: Session) -> dict:
    return {
        "fetched_at": _get_meta(session, META_FETCHED),
        "last_error": _get_meta(session, META_ERROR),
        "count": session.scalar(select(func.count()).select_from(GameCharacter)) or 0,
    }
