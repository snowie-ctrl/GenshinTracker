"""The ONLY module that talks to HoYoLAB. Converts genshin.py models to our own dataclasses
so a library or endpoint change is contained here."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence

import aiohttp
import genshin

from app.gamedata.yatta import canonical_id
from app.sync.chronicle import (
    CalendarInfo, ChallengeRunInfo, ProfileInfo, to_abyss_run, to_calendar, to_profile, to_stygian_runs,
    to_theater_runs,
)

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
    id: int = 0


@dataclass(frozen=True)
class RosterEntry:
    id: int        # our id (Traveler: element id)
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
    id: int        # our id (Traveler: element id)
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
    weekly_discounts_left: int | None = None
    weekly_discounts_max: int | None = None


class NoInventoryData(HoyolabError):
    pass


@dataclass(frozen=True)
class TalentIds:
    normal: int
    skill: int
    burst: int


@dataclass(frozen=True)
class GapCharacter:
    character_id: int
    level_current: int
    level_target: int
    talents: tuple[tuple[int, int, int], ...]
    weapon: tuple[int, int, int] | None
    avatar_id: int | None = None          # HoYoLAB id when it differs from ours (Traveler body id)
    element_attr_id: int | None = None    # Traveler only: calculator element number


@dataclass(frozen=True)
class MaterialAmount:
    id: int
    name: str
    icon: str
    rarity: int
    need: int
    short: int


@dataclass(frozen=True)
class GapResult:
    per_character: dict[int, list[MaterialAmount]]
    total: list[MaterialAmount]
    spare: list[MaterialAmount]


class HoyolabSource(Protocol):
    async def get_roster(self) -> list[RosterEntry]: ...
    async def get_details(self, raw_ids: Sequence[int]) -> list[DetailEntry]: ...
    async def get_notes(self) -> NotesInfo: ...
    async def get_talent_ids(self, avatar_id: int, element_attr_id: int | None = None) -> TalentIds: ...
    async def compute_gaps(self, chars: Sequence[GapCharacter]) -> GapResult: ...
    async def get_calendar(self) -> CalendarInfo: ...
    async def get_profile(self) -> ProfileInfo: ...
    async def get_challenges(self) -> list[ChallengeRunInfo]: ...


# --- mappers ---------------------------------------------------------------
def _weapon(w: Any) -> WeaponInfo:
    return WeaponInfo(name=w.name, icon=w.icon, rarity=int(w.rarity), level=int(w.level),
                      refinement=int(w.refinement), id=int(getattr(w, "id", 0) or 0))


def _opt_int(v: Any) -> int | None:
    return None if v is None else int(v)


def _prop(p: Any) -> str:
    return f"{p.info.name} {p.value}"


def to_roster_entry(c: Any) -> RosterEntry:
    return RosterEntry(
        id=canonical_id(c.id, c.element or None), raw_id=int(c.id), name=c.name, element=c.element or None,
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
    return DetailEntry(id=canonical_id(c.id, getattr(c, "element", None) or None), normal=normal, skill=skill,
                       burst=burst,
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
        weekly_discounts_left=_opt_int(getattr(n, "remaining_resin_discounts", None)),
        weekly_discounts_max=_opt_int(getattr(n, "max_resin_discounts", None)),
    )


def to_account(a: Any) -> Account:
    return Account(uid=int(a.uid), server=a.server, nickname=a.nickname, level=int(a.level))


def to_talent_ids(items: Sequence[Mapping]) -> TalentIds:
    upgradeable = [i for i in items if int(i.get("max_level", 1) or 1) > 1]
    if len(upgradeable) > 3:  # alternate sprint (group id order digit 3) sits between skill and burst
        upgradeable = [i for i in upgradeable if int(i["group_id"]) % 10 != 3]
    if len(upgradeable) < 3:
        raise HoyolabError("Unexpected talent list from HoYoLAB.")
    return TalentIds(int(upgradeable[0]["group_id"]), int(upgradeable[1]["group_id"]),
                     int(upgradeable[-1]["group_id"]))


def build_batch_body(chars: Sequence[GapCharacter], uid: int, region: str) -> dict:
    items = []
    for c in chars:
        item: dict[str, Any] = {
            "avatar_id": c.avatar_id or c.character_id,
            "avatar_level_current": c.level_current,
            "avatar_level_target": c.level_target,
            "skill_list": [{"id": g, "level_current": cur, "level_target": tgt} for g, cur, tgt in c.talents],
        }
        if c.weapon is not None:
            wid, cur, tgt = c.weapon
            item["weapon"] = {"id": wid, "level_current": cur, "level_target": tgt}
        if c.element_attr_id is not None:
            item["element_attr_id"] = c.element_attr_id
        items.append(item)
    return {"items": items, "uid": uid, "region": region}


def _amount(m: Mapping) -> MaterialAmount:
    return MaterialAmount(id=int(m["id"]), name=str(m.get("name") or ""), icon=str(m.get("icon") or ""),
                          rarity=int(m.get("level") or 0), need=int(m.get("num") or 0),
                          short=int(m.get("lack_num") or 0))


def to_gap_result(raw: Mapping, character_ids: list[int]) -> GapResult:
    if not raw.get("has_user_info"):
        raise NoInventoryData("HoYoLAB returned no inventory data.")
    total = [_amount(m) for m in raw.get("overall_consume") or []]
    singles = list(raw.get("single_role_result") or [])
    if not singles and len(character_ids) == 1:
        per = {character_ids[0]: total}
    elif len(singles) != len(character_ids):
        raise HoyolabError(f"Calculator returned {len(singles)} results for {len(character_ids)} characters.")
    else:
        per = {cid: [_amount(m) for m in s.get("overall_consume") or []] for cid, s in zip(character_ids, singles)}
    return GapResult(per_character=per, total=total,
                     spare=[_amount(m) for m in raw.get("available_material") or []])


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
        except (aiohttp.ClientError, TimeoutError) as e:  # offline, DNS, timeouts
            raise HoyolabError(f"Could not reach HoYoLAB ({type(e).__name__}).") from None
    raise AssertionError("unreachable")


class GenshinPySource:
    def __init__(self, cookies: dict[str, str], uid: int, delays: Sequence[float] = RETRY_DELAYS,
                 *, region: str | None = None):
        self._client = genshin.Client(cookies, game=genshin.Game.GENSHIN, uid=uid)
        self._uid = uid
        self._region = region or genshin.utility.recognize_genshin_server(uid)
        self._delays = delays

    async def get_roster(self) -> list[RosterEntry]:
        chars = await call_api(self._client.get_genshin_characters, self._uid, delays=self._delays)
        return [e for e in (to_roster_entry(c) for c in chars) if e.id is not None]

    async def get_details(self, raw_ids: Sequence[int]) -> list[DetailEntry]:
        out: list[DetailEntry] = []
        ids = list(raw_ids)
        for i in range(0, len(ids), DETAIL_BATCH):
            result = await call_api(self._client.get_genshin_detailed_characters, self._uid,
                                    characters=ids[i:i + DETAIL_BATCH], delays=self._delays)
            out.extend(e for e in (to_detail_entry(c) for c in result.characters) if e.id is not None)
        return out

    async def get_notes(self) -> NotesInfo:
        return to_notes(await call_api(self._client.get_genshin_notes, self._uid, delays=self._delays))

    async def get_talent_ids(self, avatar_id: int, element_attr_id: int | None = None) -> TalentIds:
        params: dict[str, int] = {"avatar_id": avatar_id}
        if element_attr_id is not None:
            params["element_attr_id"] = element_attr_id
        data = await call_api(self._client.request_calculator, "avatarSkill/list", method="GET",
                              params=params, delays=self._delays)
        return to_talent_ids(data.get("list") or [])

    async def compute_gaps(self, chars: Sequence[GapCharacter]) -> GapResult:
        body = build_batch_body(chars, self._uid, self._region)
        raw = await call_api(self._client.request_calculator, "batch_compute", data=body,
                             api_version=3, delays=self._delays)
        return to_gap_result(raw, [c.character_id for c in chars])

    async def get_calendar(self) -> CalendarInfo:
        return to_calendar(await call_api(self._client.get_genshin_event_calendar, self._uid,
                                          lang="en-us", delays=self._delays))

    async def get_profile(self) -> ProfileInfo:
        return to_profile(await call_api(self._client.get_partial_genshin_user, self._uid,
                                         lang="en-us", delays=self._delays))

    async def get_challenges(self) -> list[ChallengeRunInfo]:
        runs: list[ChallengeRunInfo] = []
        for previous in (False, True):
            run = to_abyss_run(await call_api(self._client.get_genshin_spiral_abyss, self._uid,
                                              previous=previous, delays=self._delays))
            if run is not None:
                runs.append(run)
        runs += to_theater_runs(await call_api(self._client.get_imaginarium_theater, self._uid,
                                               delays=self._delays))
        runs += to_stygian_runs(await call_api(self._client.get_stygian_onslaught, self._uid,
                                               delays=self._delays))
        seen: dict[tuple[str, str], ChallengeRunInfo] = {}
        for r in runs:
            seen[(r.kind, r.season)] = r
        return list(seen.values())


async def fetch_accounts(cookies: dict[str, str]) -> list[Account]:
    client = genshin.Client(cookies, game=genshin.Game.GENSHIN)
    accounts = await call_api(client.get_game_accounts)
    return [to_account(a) for a in accounts if a.game == genshin.Game.GENSHIN]
