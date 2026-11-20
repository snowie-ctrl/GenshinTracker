# backend/app/servertime.py
"""Game server time. Daily reset 04:00 server time; weekly reset Monday 04:00 server time.
All datetimes in and out are naive UTC, like everything stored in SQLite."""
from __future__ import annotations

from datetime import date, datetime, timedelta

REGION_OFFSETS = {"os_usa": -5, "os_euro": 1, "os_asia": 8, "os_cht": 8}
DEFAULT_OFFSET = 8
RESET_HOUR = 4


def offset_hours(region: str | None) -> int:
    return REGION_OFFSETS.get(region or "", DEFAULT_OFFSET)


def server_day(now: datetime, region: str | None) -> date:
    """The game day `now` belongs to: server-local time shifted back by the 04:00 reset."""
    return (now + timedelta(hours=offset_hours(region) - RESET_HOUR)).date()


def server_weekday(now: datetime, region: str | None) -> int:
    return server_day(now, region).weekday()


def week_start(now: datetime, region: str | None) -> datetime:
    """Naive UTC instant of the latest Monday 04:00 server time at or before `now`."""
    day = server_day(now, region)
    monday = day - timedelta(days=day.weekday())
    return datetime(monday.year, monday.month, monday.day) + timedelta(hours=RESET_HOUR - offset_hours(region))
