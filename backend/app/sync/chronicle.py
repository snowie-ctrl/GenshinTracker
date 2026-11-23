"""Map genshin.py Battle Chronicle models to our own dataclasses. Pure: no network.
Identity fields (nickname, server, avatars) are dropped here and never leave this module."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.gamedata.yatta import canonical_id
from app.timeutil import iso

POOLS = (("character_banners", "character"), ("weapon_banners", "weapon"), ("chronicled_banners", "chronicled"))
CHALLENGE_KINDS = (("abyss_detail", "abyss"), ("theater_detail", "theater"), ("stygian_detail", "stygian"))
CHESTS = ("common", "exquisite", "precious", "luxurious", "remarkable")
OCULI = ("anemoculi", "geoculi", "electroculi", "dendroculi", "hydroculi", "pyroculi", "cryoculi", "lunoculi")
TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class BannerItem:
    id: int
    name: str
    icon: str
    rarity: int
    kind: str                       # character | weapon


@dataclass(frozen=True)
class LiveBanner:
    id: int
    pool: str                       # character | weapon | chronicled
    name: str
    version: str
    start: str | None
    end: str | None
    items: list[BannerItem]


@dataclass(frozen=True)
class Reward:
    id: int
    name: str
    icon: str
    count: int
    rarity: int


@dataclass(frozen=True)
class EventInfo:
    id: int
    name: str
    description: str
    start: str | None
    end: str | None
    rewards: list[Reward]
    finished: bool = False          # HoYoLAB says the player completed it


@dataclass(frozen=True)
class ChallengePeriod:
    kind: str                       # abyss | theater | stygian
    name: str
    start: str | None
    end: str | None


@dataclass(frozen=True)
class CalendarInfo:
    banners: list[LiveBanner]
    events: list[EventInfo]
    challenges: list[ChallengePeriod]


@dataclass(frozen=True)
class Offering:
    name: str
    level: int


@dataclass(frozen=True)
class RegionInfo:
    id: int
    name: str
    explored: float                 # percent, one decimal
    reputation: int | None
    offerings: list[Offering]


@dataclass(frozen=True)
class ProfileStats:
    ar: int
    days_active: int
    achievements: int
    characters: int
    chests: dict[str, int]
    oculi: dict[str, int]
    waypoints: int
    domains: int


@dataclass(frozen=True)
class ProfileInfo:
    stats: ProfileStats
    regions: list[RegionInfo]


@dataclass(frozen=True)
class ChallengeRunInfo:
    kind: str
    season: str
    start: str | None
    end: str | None
    summary: dict
    teams: list[list[int]] = field(default_factory=list)


def _ts(value: Any) -> str | None:
    ts = int(value or 0)
    return iso(datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)) if ts > 0 else None


def _dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return iso(value)


def _plain(text: str) -> str:
    return " ".join(TAG.sub(" ", text or "").split())


def _team(chars: Any) -> list[int]:
    return [cid for c in chars if (cid := canonical_id(c.id, getattr(c, "element", None) or None)) is not None]


def _banner(b: Any, pool: str) -> LiveBanner:
    items = [BannerItem(cid, c.name, c.icon, int(c.rarity), "character") for c in b.characters
             if (cid := canonical_id(c.id, getattr(c, "element", None) or None)) is not None]
    items += [BannerItem(int(w.id), w.name, w.icon, int(w.rarity), "weapon") for w in b.weapons]
    return LiveBanner(int(b.id), pool, b.name, str(b.version or ""), _ts(b.start_timestamp), _ts(b.end_timestamp), items)


def to_calendar(cal: Any) -> CalendarInfo:
    banners = [_banner(b, pool) for attr, pool in POOLS for b in getattr(cal, attr, None) or []]
    events = [EventInfo(int(e.id), e.name, _plain(e.description), _ts(e.start_timestamp), _ts(e.end_timestamp),
                        [Reward(int(r.id), r.name, r.icon, int(r.num), int(r.rarity)) for r in e.rewards],
                        bool(getattr(e, "is_finished", False)))
              for e in cal.events]
    challenges = []
    for e in cal.challenges:
        kind = next((k for attr, k in CHALLENGE_KINDS if getattr(e, attr, None) is not None), None)
        if kind is not None:
            challenges.append(ChallengePeriod(kind, e.name, _ts(e.start_timestamp), _ts(e.end_timestamp)))
    return CalendarInfo(banners, events, challenges)


def to_profile(user: Any) -> ProfileInfo:
    s = user.stats
    stats = ProfileStats(
        ar=int(user.info.level), days_active=int(s.days_active), achievements=int(s.achievements),
        characters=int(s.characters),
        chests={c: int(getattr(s, f"{c}_chests", 0) or 0) for c in CHESTS},
        oculi={o: int(getattr(s, o, 0) or 0) for o in OCULI},
        waypoints=int(s.unlocked_waypoints), domains=int(s.unlocked_domains),
    )
    regions = [RegionInfo(int(e.id), e.name, round(int(e.raw_explored) / 10, 1),
                          int(e.level) if e.type == "Reputation" else None,
                          [Offering(o.name, int(o.level)) for o in e.offerings])
               for e in user.explorations if int(getattr(e, "parent_id", 0) or 0) == 0]
    return ProfileInfo(stats, regions)


def to_abyss_run(a: Any) -> ChallengeRunInfo | None:
    if not a.unlocked or int(a.total_battles) == 0:
        return None
    teams = [_team(b.characters)
             for f in a.floors for ch in f.chambers for b in ch.battles]
    return ChallengeRunInfo("abyss", str(a.season), _dt(a.start_time), _dt(a.end_time),
                            {"stars": int(a.total_stars), "max_floor": a.max_floor,
                             "wins": int(a.total_wins), "battles": int(a.total_battles)}, teams)


def to_theater_runs(t: Any) -> list[ChallengeRunInfo]:
    if not t.unlocked:
        return []
    runs = []
    for d in t.datas:
        if not d.has_data:
            continue
        runs.append(ChallengeRunInfo(
            "theater", str(d.schedule.id), _dt(d.schedule.start_datetime), _dt(d.schedule.end_datetime),
            {"act": int(d.stats.best_record), "difficulty": int(d.stats.difficulty), "medals": int(d.stats.medal_num)},
            [_team(act.characters) for act in d.acts]))
    return runs


def to_stygian_runs(items: Any) -> list[ChallengeRunInfo]:
    runs = []
    for h in items or []:
        data = h.single_player
        if not data.has_data:
            continue
        summary = ({"difficulty": int(data.best_record.difficulty), "time_used": int(data.best_record.time_used)}
                   if data.best_record is not None else {})
        runs.append(ChallengeRunInfo("stygian", str(h.season.id), _dt(h.season.start_at), _dt(h.season.end_at),
                                     summary, [_team(ch.team) for ch in data.challenges]))
    return runs


def to_json(obj: Any) -> dict:
    return asdict(obj)


def character_ids(info: CalendarInfo | list[ChallengeRunInfo]) -> set[int]:
    if isinstance(info, CalendarInfo):
        return {i.id for b in info.banners for i in b.items if i.kind == "character"}
    return {cid for run in info for team in run.teams for cid in team}
