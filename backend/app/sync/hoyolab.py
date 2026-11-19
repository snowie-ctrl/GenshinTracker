"""The ONLY module that talks to HoYoLAB. Converts genshin.py models to our own dataclasses
so a library or endpoint change is contained here."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol, Sequence

import genshin

from app.gamedata.yatta import canonical_id

RETRY_DELAYS: tuple[float, ...] = (2.0, 5.0, 10.0)
DETAIL_BATCH = 20


class HoyolabError(Exception):
    """Any HoYoLAB failure. Messages never contain cookie values."""


class AuthExpired(HoyolabError):
    pass


class RateLimited(HoyolabError):
    pass


@dataclass(frozen=True)
class Account:
    uid: int
    server: str
    nickname: str
    level: int


@dataclass(frozen=True)
class WeaponInfo:
    name: str
    icon: str
    rarity: int
    level: int
    refinement: int


@dataclass(frozen=True)
class RosterEntry:
    id: int        # canonical id
    raw_id: int    # id HoYoLAB uses (needed for detail requests)
    name: str
    element: str | None
    level: int
    constellation: int
    friendship: int
    weapon: WeaponInfo


@dataclass(frozen=True)
class ArtifactInfo:
    slot: int
    set_name: str
    rarity: int
    level: int
    main_stat: str
    substats: list[str]
    icon: str


@dataclass(frozen=True)
class DetailEntry:
    id: int
    normal: int
    skill: int
    burst: int
    weapon: WeaponInfo
    artifacts: list[ArtifactInfo]
    stats: list[dict]


@dataclass(frozen=True)
class ExpeditionInfo:
    icon: str
    finished: bool
    remaining_seconds: int


@dataclass(frozen=True)
class NotesInfo:
    resin: int
    resin_max: int
    resin_recovery_seconds: int
    commissions_done: int
    commissions_max: int
    realm_currency: int
    realm_currency_max: int
    expeditions: list[ExpeditionInfo]


class HoyolabSource(Protocol):
    async def get_roster(self) -> list[RosterEntry]: ...
    async def get_details(self, raw_ids: Sequence[int]) -> list[DetailEntry]: ...
    async def get_notes(self) -> NotesInfo: ...


# --- mappers ---------------------------------------------------------------
def _weapon(w: Any) -> WeaponInfo:
    return WeaponInfo(name=w.name, icon=w.icon, rarity=int(w.rarity), level=int(w.level),
                      refinement=int(w.refinement))


def _prop(p: Any) -> str:
    return f"{p.info.name} {p.value}"


def to_roster_entry(c: Any) -> RosterEntry:
    return RosterEntry(
        id=canonical_id(c.id), raw_id=int(c.id), name=c.name, element=c.element or None,
        level=int(c.level), constellation=int(c.constellation), friendship=int(c.friendship),
        weapon=_weapon(c.weapon),
    )


def to_detail_entry(c: Any) -> DetailEntry:
    # Active skills arrive as: normal, skill, [alternate sprint], burst. Burst is always last.
    levels = [int(s.level) for s in c.skills if s.skill_type == 1]
    normal = levels[0] if levels else 1
    skill = levels[1] if len(levels) > 1 else 1
    burst = levels[-1] if len(levels) >= 3 else 1
    artifacts = [
        ArtifactInfo(slot=int(a.pos), set_name=a.set.name, rarity=int(a.rarity), level=int(a.level),
                     main_stat=_prop(a.main_stat), substats=[_prop(s) for s in a.sub_stats], icon=a.icon)
        for a in c.artifacts
    ]
    stats = [{"name": p.info.name, "value": p.final} for p in [*c.base_properties, *c.extra_properties]]
    return DetailEntry(id=canonical_id(c.id), normal=normal, skill=skill, burst=burst,
                       weapon=_weapon(c.weapon), artifacts=artifacts, stats=stats)


def to_notes(n: Any) -> NotesInfo:
    return NotesInfo(
        resin=int(n.current_resin), resin_max=int(n.max_resin),
        resin_recovery_seconds=int(n.remaining_resin_recovery_time.total_seconds()),
        commissions_done=int(n.completed_commissions), commissions_max=int(n.max_commissions),
        realm_currency=int(n.current_realm_currency), realm_currency_max=int(n.max_realm_currency),
        expeditions=[
            ExpeditionInfo(icon=e.character_icon, finished=e.status == "Finished",
                           remaining_seconds=int(e.remaining_time.total_seconds()))
            for e in n.expeditions
        ],
    )


def to_account(a: Any) -> Account:
    return Account(uid=int(a.uid), server=a.server, nickname=a.nickname, level=int(a.level))


# --- calls -----------------------------------------------------------------
async def call_api(fn: Callable[..., Awaitable[Any]], *args: Any,
                   delays: Sequence[float] = RETRY_DELAYS, **kwargs: Any) -> Any:
    """Call genshin.py, retrying rate limits; map errors to ours (without chaining request info)."""
    for attempt in range(len(delays) + 1):
        try:
            return await fn(*args, **kwargs)
        except (genshin.errors.TooManyRequests, genshin.errors.VisitsTooFrequently) as e:
            if attempt == len(delays):
                raise RateLimited(str(e)) from None
            await asyncio.sleep(delays[attempt])
        except genshin.errors.InvalidCookies as e:
            raise AuthExpired(str(e)) from None
        except genshin.errors.GenshinException as e:
            raise HoyolabError(str(e)) from None
    raise AssertionError("unreachable")


class GenshinPySource:
    def __init__(self, cookies: dict[str, str], uid: int, delays: Sequence[float] = RETRY_DELAYS):
        self._client = genshin.Client(cookies, game=genshin.Game.GENSHIN, uid=uid)
        self._uid = uid
        self._delays = delays

    async def get_roster(self) -> list[RosterEntry]:
        chars = await call_api(self._client.get_genshin_characters, self._uid, delays=self._delays)
        return [to_roster_entry(c) for c in chars]

    async def get_details(self, raw_ids: Sequence[int]) -> list[DetailEntry]:
        out: list[DetailEntry] = []
        ids = list(raw_ids)
        for i in range(0, len(ids), DETAIL_BATCH):
            result = await call_api(self._client.get_genshin_detailed_characters, self._uid,
                                    characters=ids[i:i + DETAIL_BATCH], delays=self._delays)
            out.extend(to_detail_entry(c) for c in result.characters)
        return out

    async def get_notes(self) -> NotesInfo:
        return to_notes(await call_api(self._client.get_genshin_notes, self._uid, delays=self._delays))


async def fetch_accounts(cookies: dict[str, str]) -> list[Account]:
    client = genshin.Client(cookies, game=genshin.Game.GENSHIN)
    accounts = await call_api(client.get_game_accounts)
    return [to_account(a) for a in accounts if a.game == genshin.Game.GENSHIN]
