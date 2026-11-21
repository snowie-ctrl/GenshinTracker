"""Shared wish vocabulary: pools, pity rules, the normalized incoming row, time helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, GameWeapon

POOL_BY_GACHA_TYPE = {"100": "beginner", "200": "standard", "301": "character",
                      "400": "character", "302": "weapon", "500": "chronicled"}
POOLS = ("character", "weapon", "chronicled", "standard", "beginner")
SINGLE_TYPE = {"beginner": "100", "standard": "200", "weapon": "302", "chronicled": "500"}
TIME_FMT = "%Y-%m-%d %H:%M:%S"
UID_MISMATCH = "This wish history belongs to a different account."
NEEDS_UID = "Connect HoYoLAB in Settings first, so imports can be checked against your UID."
BAD_ROWS_SHOWN = 50


def bad_rows_message(errors: list[str]) -> str:
    shown = "; ".join(errors[:BAD_ROWS_SHOWN])
    more = f" (and {len(errors) - BAD_ROWS_SHOWN} more)" if len(errors) > BAD_ROWS_SHOWN else ""
    return f"Nothing was imported: {len(errors)} row(s) could not be read: {shown}{more}"


@dataclass(frozen=True)
class PityRule:
    hard: int
    soft: int | None
    four: int


PITY = {
    "character": PityRule(90, 74, 10),
    "weapon": PityRule(80, 63, 10),
    "standard": PityRule(90, 74, 10),
    "chronicled": PityRule(90, 74, 10),
    "beginner": PityRule(50, None, 10),
}


@dataclass(frozen=True)
class IncomingWish:
    id: str | None
    pool: str
    gacha_type: str | None
    time: str
    name: str
    item_type: str
    rarity: int


class ImportFailed(Exception):
    """An import that must not change anything. `message` is shown to the user verbatim."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def normalize_time(value: str | datetime) -> str:
    if isinstance(value, datetime):
        return value.strftime(TIME_FMT)
    text = str(value).strip().replace("T", " ")
    return datetime.strptime(text[:19], TIME_FMT).strftime(TIME_FMT)


def shift_time(time: str, from_offset: int, to_offset: int) -> str:
    return (datetime.strptime(time, TIME_FMT) + timedelta(hours=to_offset - from_offset)).strftime(TIME_FMT)


def to_utc_seconds(time: str, offset: int) -> int:
    local = datetime.strptime(time, TIME_FMT).replace(tzinfo=timezone(timedelta(hours=offset)))
    return int(local.timestamp())


def server_local_now(now_utc: datetime, offset: int) -> str:
    return (now_utc + timedelta(hours=offset)).strftime(TIME_FMT)


def item_type_of(value: str) -> str:
    v = str(value).strip().lower()
    if v in ("character", "weapon"):
        return v
    raise ValueError(f"unknown item type {value!r} (export in English)")


class ItemResolver:
    def __init__(self, by_name: dict[str, int]):
        self._by_name = by_name

    @classmethod
    def from_session(cls, session: Session) -> "ItemResolver":
        by_name = {name.casefold(): wid for wid, name in session.execute(select(GameWeapon.id, GameWeapon.name))}
        by_name.update({name.casefold(): cid for cid, name in
                        session.execute(select(GameCharacter.id, GameCharacter.name))})
        return cls(by_name)

    def resolve(self, name: str) -> int | None:
        return self._by_name.get(name.casefold())
