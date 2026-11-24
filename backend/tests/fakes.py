import asyncio
from datetime import datetime, timedelta

from app.sync.chronicle import CalendarInfo, ProfileInfo, ProfileStats
from app.sync.hoyolab import (
    ArtifactInfo, DetailEntry, ExpeditionInfo, GapResult, MaterialAmount, NotesInfo, RosterEntry, TalentIds,
    WeaponInfo,
)

WEAPON = WeaponInfo("The Flute", "https://act-webstatic.hoyoverse.com/w.png", 4, 90, 5, 1)
NOTES = NotesInfo(153, 200, 3600, 4, 4, 1460, 2400,
                  [ExpeditionInfo("https://act-webstatic.hoyoverse.com/e.png", False, 7200)])


def make_roster(id: int, level: int = 80, raw_id: int | None = None, name: str = "Char",
                element: str | None = "Pyro") -> RosterEntry:
    return RosterEntry(id=id, raw_id=raw_id or id, name=name, element=element, level=level,
                       constellation=2, friendship=10, weapon=WEAPON)


def make_detail(id: int, talents: tuple[int, int, int] = (6, 8, 8)) -> DetailEntry:
    artifact = ArtifactInfo(1, "Noblesse Oblige", 5, 20, "HP 4780", ["CRIT Rate 3.9%"],
                            "https://act-webstatic.hoyoverse.com/a.png")
    return DetailEntry(id, *talents, WEAPON, [artifact], [{"name": "HP", "value": "20000"}])


class FakeSource:
    """Stand-in for GenshinPySource. `fail` maps part name -> exception to raise."""

    def __init__(self, roster=None, notes=NOTES, fail=None, gate: asyncio.Event | None = None,
                 gaps: GapResult | None = None, gaps_gate: asyncio.Event | None = None,
                 calendar=None, profile=None, challenges=None, announcements=None):
        self.roster = roster if roster is not None else [
            make_roster(10000032, name="Bennett"), make_roster(10000089, level=90, name="Furina"),
        ]
        self.notes = notes
        self.fail = fail or {}
        self.gate = gate
        self.gaps = gaps
        self.gaps_gate = gaps_gate
        self.calendar = calendar
        self.profile = profile
        self.challenges = challenges
        self.announcements = announcements
        self.calls: list = []

    async def get_roster(self):
        self.calls.append("roster")
        if self.gate is not None:
            await self.gate.wait()
        if "roster" in self.fail:
            raise self.fail["roster"]
        return list(self.roster)

    async def get_details(self, raw_ids):
        self.calls.append(("details", tuple(raw_ids)))
        if "details" in self.fail:
            raise self.fail["details"]
        return [make_detail(r.id) for r in self.roster if r.raw_id in raw_ids]

    async def get_notes(self):
        self.calls.append("notes")
        if "notes" in self.fail:
            raise self.fail["notes"]
        return self.notes

    async def get_talent_ids(self, avatar_id, element_attr_id=None):
        self.calls.append(("talents", avatar_id, element_attr_id) if element_attr_id else ("talents", avatar_id))
        if "talents" in self.fail:
            raise self.fail["talents"]
        return TalentIds(avatar_id * 10 + 1, avatar_id * 10 + 2, avatar_id * 10 + 9)

    async def compute_gaps(self, chars):
        self.calls.append(("gaps", tuple(c.character_id for c in chars)))
        if self.gaps_gate is not None:
            await self.gaps_gate.wait()
        if "gaps" in self.fail:
            raise self.fail["gaps"]
        if self.gaps is not None:
            return self.gaps
        guide = MaterialAmount(104302, "Guide to Freedom", "", 3, 9, 4)
        return GapResult(per_character={c.character_id: [guide] for c in chars},
                         total=[MaterialAmount(104302, "Guide to Freedom", "", 3, 9 * len(chars), 4 * len(chars))],
                         spare=[])

    async def get_calendar(self):
        self.calls.append("calendar")
        if "calendar" in self.fail:
            raise self.fail["calendar"]
        return self.calendar if self.calendar is not None else CalendarInfo([], [], [])

    async def get_profile(self):
        self.calls.append("profile")
        if "profile" in self.fail:
            raise self.fail["profile"]
        return self.profile if self.profile is not None else ProfileInfo(
            ProfileStats(60, 100, 500, 40, {}, {}, 300, 50), [])

    async def get_challenges(self):
        self.calls.append("challenges")
        if "challenges" in self.fail:
            raise self.fail["challenges"]
        return list(self.challenges or [])

    async def get_announcements(self):
        self.calls.append("announcements")
        if "announcements" in self.fail:
            raise self.fail["announcements"]
        return list(self.announcements or [])


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)
