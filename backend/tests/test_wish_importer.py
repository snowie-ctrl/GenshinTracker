import asyncio
import json
import logging
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.db.models import Wish, WishImport
from app.wishes import importer as importer_mod
from app.wishes.authkey import CACHE_LOCKED
from app.wishes.fetch import LINK_EXPIRED
from app.wishes.importer import INTERRUPTED, ImportBusy, WishImporter
from app.wishes.types import NEEDS_UID, UID_MISMATCH, ImportFailed
from wishdata import (FakeGachaApi, fake_link, make_paimon_xlsx, raw_wish, uigf_bytes, wish_url,
                      write_env)

GAME = [raw_wish(str(1704880800000000000 + i), "302", f"2024-01-10 10:00:{i:02d}", "Slingshot", 3)
        for i in range(5)] + [raw_wish("1704880800000000100", "301", "2024-01-10 11:00:00", "Furina", 5,
                                       "Character")]


async def no_sleep(_s):
    return None


def make(paths, sf, page=None, api=None, link_error=None):
    unknown: list[set[str]] = []

    def reader(game_path: str):
        if link_error:
            raise ImportFailed(link_error)
        return fake_link()

    async def on_unknown(names):
        unknown.append(names)

    imp = WishImporter(sf, paths, reader, lambda link: page or api.page, on_unknown, sleep=no_sleep)
    imp.unknown = unknown
    return imp


def count(sf, model=Wish):
    with sf() as s:
        return s.scalar(select(func.count()).select_from(model))


async def run_game(imp):
    await imp.start_game()
    await imp.wait()
    return imp.status()["last"]


async def test_game_import_backs_up_merges_and_snapshots(paths, session_factory):
    write_env(paths)
    imp = make(paths, session_factory, api=FakeGachaApi(GAME))
    last = await run_game(imp)
    assert last["ok"] is True and last["added"] == 6 and imp.running is False
    assert len(list(paths.wish_backups.glob("tracker-*.db"))) == 1
    (snap,) = paths.wish_backups.glob("uigf-*.json")
    assert len(json.loads(snap.read_text("utf-8"))["hk4e"][0]["list"]) == 6
    assert list(paths.backups.glob("tracker-*.db")) == []          # sync backups untouched
    assert (await run_game(imp))["added"] == 0                      # incremental: stops at known ids


async def test_expired_link_changes_nothing(paths, session_factory):
    write_env(paths)
    last = await run_game(make(paths, session_factory, api=FakeGachaApi(GAME, expire_after=0)))
    assert last["ok"] is False and last["error"] == LINK_EXPIRED
    assert count(session_factory) == 0


async def test_locked_cache_message_and_no_backup(paths, session_factory):
    write_env(paths)
    last = await run_game(make(paths, session_factory, api=FakeGachaApi(GAME), link_error=CACHE_LOCKED))
    assert last["error"] == CACHE_LOCKED
    assert list(paths.wish_backups.glob("*")) == []


async def test_other_account_is_refused(paths, session_factory):
    write_env(paths)
    rows = [raw_wish("1704880800000000001", "302", "2024-01-10 10:00:00", "Slingshot", 3, uid=800000002)]
    last = await run_game(make(paths, session_factory, api=FakeGachaApi(rows)))
    assert last["error"] == UID_MISMATCH and count(session_factory) == 0


async def test_needs_uid(paths, session_factory):
    last = await run_game(make(paths, session_factory, api=FakeGachaApi(GAME)))
    assert last["error"] == NEEDS_UID


async def test_unexpected_error_never_exposes_the_url(paths, session_factory, caplog):
    caplog.set_level(logging.DEBUG)
    write_env(paths)

    async def page(gacha_type, end_id):
        raise RuntimeError(f"request to {wish_url()} failed")
    last = await run_game(make(paths, session_factory, page=page))
    assert last["error"] == "Import failed (RuntimeError)."
    assert "SECRET-AUTHKEY" not in caplog.text


async def test_single_flight(paths, session_factory):
    write_env(paths)
    gate = asyncio.Event()

    async def page(gacha_type, end_id):
        await gate.wait()
        return []
    imp = make(paths, session_factory, page=page)
    first = await imp.start_game()
    assert await imp.start_game() == first
    with pytest.raises(ImportBusy):
        await imp.import_file("x.json", b"{}")
    gate.set()
    await imp.wait()
    assert count(session_factory, WishImport) == 1


async def test_paimon_file_twice(paths, session_factory):
    write_env(paths)
    imp = make(paths, session_factory)
    content = make_paimon_xlsx({"Weapon Event": [("Weapon", "Slingshot", "2024-01-10 10:00:00", 3),
                                                 ("Weapon", "Mystery Blade", "2024-01-10 10:00:00", 3)]})
    assert (await imp.import_file("paimon.xlsx", content))["last"]["added"] == 2
    assert imp.unknown == [{"Slingshot", "Mystery Blade"}]
    assert (await imp.import_file("paimon.xlsx", content))["last"]["added"] == 0


async def test_bad_json_file(paths, session_factory):
    write_env(paths)
    status = await make(paths, session_factory).import_file("x.json", b"not json")
    assert status["last"]["error"] == "This file is not a UIGF export."


async def test_backup_and_snapshot_rotation_keep_ten(paths, session_factory):
    write_env(paths)
    imp = make(paths, session_factory)
    for _ in range(12):
        await imp.import_file("u.json", uigf_bytes([]))
    assert len(list(paths.wish_backups.glob("tracker-*.db"))) == 10
    assert len(list(paths.wish_backups.glob("uigf-*.json"))) == 10


async def test_merge_failure_rolls_back(paths, session_factory, monkeypatch):
    write_env(paths)

    def broken_merge(session, incoming, source, now):
        session.add(Wish(id=None, pool="standard", gacha_type="200", time="2024-01-01 00:00:00", seq=0,
                         name="X", item_id=None, item_type="weapon", rarity=3, source="uigf", imported_at=now))
        session.flush()
        raise RuntimeError("boom")
    monkeypatch.setattr(importer_mod, "merge", broken_merge)
    status = await make(paths, session_factory).import_file("u.json", uigf_bytes([]))
    assert status["last"]["error"] == "Import failed (RuntimeError)."
    assert count(session_factory) == 0


def test_interrupted_imports_are_closed_on_start(paths, session_factory):
    with session_factory.begin() as s:
        s.add(WishImport(started_at=datetime(2024, 1, 1), source="game", ok=None, added=0, upgraded=0, skipped=0))
    imp = make(paths, session_factory)
    last = imp.status()["last"]
    assert last["ok"] is False and last["error"] == INTERRUPTED


def test_cache_status_hides_link(paths, session_factory):
    assert make(paths, session_factory).cache_status()["status"] == "found"
    assert make(paths, session_factory, link_error=CACHE_LOCKED).cache_status()["status"] == "locked"
