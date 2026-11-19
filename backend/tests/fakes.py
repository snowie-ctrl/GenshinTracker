import asyncio
from datetime import datetime, timedelta

from app.sync.hoyolab import (
    ArtifactInfo, DetailEntry, ExpeditionInfo, NotesInfo, RosterEntry, WeaponInfo,
)

WEAPON = WeaponInfo("The Flute", "https://act-webstatic.hoyoverse.com/w.png", 4, 90, 5)
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

    def __init__(self, roster=None, notes=NOTES, fail=None, gate: asyncio.Event | None = None):
        self.roster = roster if roster is not None else [
            make_roster(10000032, name="Bennett"), make_roster(10000089, level=90, name="Furina"),
        ]
        self.notes = notes
        self.fail = fail or {}
        self.gate = gate
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


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)
