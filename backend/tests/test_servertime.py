# backend/tests/test_servertime.py
from datetime import datetime

import pytest

from app.servertime import offset_hours, server_weekday, week_start


@pytest.mark.parametrize("region,before,after", [
    ("os_euro", datetime(2026, 11, 23, 2, 59), datetime(2026, 11, 23, 3, 0)),
    ("os_usa", datetime(2026, 11, 23, 8, 59), datetime(2026, 11, 23, 9, 0)),
    ("os_asia", datetime(2026, 11, 22, 19, 59), datetime(2026, 11, 22, 20, 0)),
    ("os_cht", datetime(2026, 11, 22, 19, 59), datetime(2026, 11, 22, 20, 0)),
])
def test_day_changes_at_0400_server_time(region, before, after):
    assert server_weekday(before, region) == 6  # still Sunday
    assert server_weekday(after, region) == 0   # Monday after reset


def test_unknown_region_defaults_to_utc_plus_8():
    assert offset_hours(None) == 8
    assert offset_hours("something") == 8


def test_week_start_is_latest_monday_reset():
    assert week_start(datetime(2026, 11, 25, 12, 0), "os_euro") == datetime(2026, 11, 23, 3, 0)
    assert week_start(datetime(2026, 11, 23, 2, 0), "os_euro") == datetime(2026, 11, 16, 3, 0)
    assert week_start(datetime(2026, 11, 23, 9, 0), "os_usa") == datetime(2026, 11, 23, 9, 0)
    assert week_start(datetime(2026, 11, 23, 8, 59), "os_usa") == datetime(2026, 11, 16, 9, 0)
