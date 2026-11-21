# backend/tests/test_wish_fetch.py
import pytest

from app.wishes.fetch import FETCH_TYPES, FetchFailed, WishLinkExpired, fetch_new, record_uid, to_incoming
from wishdata import FAKE_UID, FakeGachaApi, raw_wish


def weapon_rows(n: int, start_id: int = 1_700_000_000_000_000_000) -> list[dict]:
    return [raw_wish(str(start_id + i), "302", f"2024-01-01 10:{i // 60:02d}:{i % 60:02d}", "Slingshot", 3)
            for i in range(n)]


async def no_sleep(_s):
    return None


async def test_pages_until_short_page_and_dedupes_301_400():
    char = [raw_wish("1700000000000000101", "301", "2024-01-02 10:00:00", "Furina", 5, "Character"),
            raw_wish("1700000000000000102", "400", "2024-01-02 10:00:01", "Bennett", 4, "Character")]
    api = FakeGachaApi(weapon_rows(45) + char)
    out = await fetch_new(api.page, set(), sleep=no_sleep)
    assert len(out) == 47
    assert len({r["id"] for r in out}) == 47
    assert [c[0] for c in api.calls].count("302") == 3          # 20 + 20 + 5
    assert {c[0] for c in api.calls} == set(FETCH_TYPES)


async def test_stops_at_first_known_id():
    rows = weapon_rows(45)
    known = {r["id"] for r in rows[:30]}                          # oldest 30 already stored
    api = FakeGachaApi(rows)
    out = await fetch_new(api.page, known, sleep=no_sleep)
    assert sorted(r["id"] for r in out) == sorted(r["id"] for r in rows[30:])
    assert [c for c in api.calls if c[0] == "302"] == [("302", "0")]   # first page already hit a known id


async def test_rate_limit_is_retried_then_fails():
    api = FakeGachaApi(weapon_rows(3), rate_limit_times=2)
    assert len(await fetch_new(api.page, set(), sleep=no_sleep)) == 3
    api = FakeGachaApi(weapon_rows(3), rate_limit_times=10)
    with pytest.raises(FetchFailed) as e:
        await fetch_new(api.page, set(), sleep=no_sleep)
    assert e.value.kind == "RateLimited"


async def test_expired_link_propagates():
    api = FakeGachaApi(weapon_rows(45), expire_after=1)
    with pytest.raises(WishLinkExpired):
        await fetch_new(api.page, set(), sleep=no_sleep)


def test_to_incoming_and_uid():
    raw = raw_wish("1700000000000000101", "400", "2024-01-02 10:00:00", "Furina", 5, "Character")
    w = to_incoming(raw)
    assert (w.id, w.pool, w.gacha_type, w.time, w.name, w.item_type, w.rarity) == (
        "1700000000000000101", "character", "400", "2024-01-02 10:00:00", "Furina", "character", 5)
    assert record_uid([raw]) == FAKE_UID and record_uid([]) is None
