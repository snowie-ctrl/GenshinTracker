# backend/tests/test_api_wishes.py
import json
import logging
import time
from datetime import datetime, timedelta

from app.db.models import GameBanner, GameWeapon
from app.timeutil import utcnow
from app.wishes import authkey as ak
from app.wishes.types import ImportFailed, NEEDS_UID
from helpers import make_client, seed_game
from wishdata import (FAKE_AUTHKEY, FakeGachaApi, fake_link, make_game_install, make_paimon_xlsx, raw_wish,
                      wish_url, write_env)

MIST, DREAMS = 11509, 14504


def wait_import(client, timeout=5.0):
    deadline = time.monotonic() + timeout
    while True:
        st = client.get("/api/wishes/import/status").json()
        if not st["running"]:
            return st
        assert time.monotonic() < deadline, "import never finished"
        time.sleep(0.02)


def game_rows():
    rows = [raw_wish(str(1704880800000000000 + i), "200", f"2024-01-10 10:{i // 60:02d}:{i % 60:02d}",
                     "Slingshot", 3) for i in range(60)]
    rows.append(raw_wish("1704880800000000100", "301", "2024-01-11 10:00:00", "Furina", 5, "Character"))
    return rows


def client_with(paths, api=None, reader=None):
    return make_client(paths, wish_link_reader=reader or (lambda game_path: fake_link()),
                       wish_page_factory=lambda link: api.page if api else None)


def seed_current_weapon_banner(client):
    sf = client.app.state.ctx.session_factory
    local = utcnow() + timedelta(hours=1)        # os_euro server time
    start = (local - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    end = (local + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    with sf.begin() as s:
        s.add(GameWeapon(id=MIST, name="Mistsplitter Reforged", icon="UI_EquipIcon_Sword_Narukami", rarity=5,
                         weapon_type="Sword"))
        s.add(GameWeapon(id=DREAMS, name="A Thousand Floating Dreams", icon="UI_EquipIcon_Catalyst_Ayus",
                         rarity=5, weapon_type="Catalyst"))
        s.add(GameBanner(key=f"weapon|{start}|0", pool="weapon", name="Epitome Invocation", short_name="Mist",
                         start=start, end=end, timezone_dependent=False, timezone_dependent_end=False, order=0,
                         featured_5=[MIST, DREAMS], featured_4=[], version="9.9"))


def test_game_import_summary_history_and_dashboard(paths):
    write_env(paths)
    with client_with(paths, FakeGachaApi(game_rows())) as client:
        seed_game(client.app.state.ctx.session_factory)
        assert client.post("/api/wishes/import/game").status_code == 200
        st = wait_import(client)
        assert st["last"]["ok"] is True and st["last"]["added"] == 61
        summary = client.get("/api/wishes/summary").json()
        pools = {p["pool"]: p for p in summary["pools"]}
        assert set(pools) == {"standard", "character"}
        assert pools["standard"]["pity5"] == 60 and pools["standard"]["in_soft"] is False
        assert pools["character"]["fives"][0]["name"] == "Furina"
        assert pools["character"]["fives"][0]["outcome"] == "unknown"        # no banner data yet
        assert summary["overall"]["pulls"] == 61 and summary["banners_available"] is False
        page1 = client.get("/api/wishes?pool=standard").json()
        assert page1["total"] == 60 and len(page1["rows"]) == 50 and page1["page_size"] == 50
        assert len(client.get("/api/wishes?pool=standard&page=2").json()["rows"]) == 10
        five = client.get("/api/wishes?rarity=5").json()
        assert five["total"] == 1 and five["rows"][0]["pity"] == 1
        assert client.get("/api/wishes?q=furi").json()["total"] == 1
        dash = client.get("/api/dashboard").json()["pity"]
        assert {"pool": "standard", "pity5": 60, "hard": 90, "next_state": None, "fate_points": None} in dash


def test_upload_paimon_then_export_round_trip(paths):
    write_env(paths)
    content = make_paimon_xlsx({"Weapon Event": [("Weapon", "Slingshot", "2024-01-10 10:00:00", 3)] * 2})
    with client_with(paths) as client:
        r = client.post("/api/wishes/import/file", files={"file": ("paimon.xlsx", content)})
        assert r.status_code == 200 and r.json()["last"]["added"] == 2
        exp = client.get("/api/wishes/export")
        assert exp.status_code == 200
        assert 'filename="genshintracker-uigf-' in exp.headers["content-disposition"]
        r = client.post("/api/wishes/import/file", files={"file": ("again.json", exp.content)})
        assert r.json()["last"]["ok"] is True and r.json()["last"]["added"] == 0


def test_upload_validation(paths, monkeypatch):
    write_env(paths)
    with client_with(paths) as client:
        assert client.post("/api/wishes/import/file", files={"file": ("x.csv", b"a")}).status_code == 400
        monkeypatch.setattr("app.api.wishes.WISH_UPLOAD_MAX_BYTES", 10)
        assert client.post("/api/wishes/import/file", files={"file": ("x.json", b"x" * 11)}).status_code == 413


def test_export_needs_uid(paths):
    with client_with(paths) as client:
        r = client.get("/api/wishes/export")
    assert r.status_code == 400 and r.json()["detail"] == NEEDS_UID


def test_chart_validation_and_fate(paths):
    write_env(paths)
    with client_with(paths) as client:
        seed_current_weapon_banner(client)
        assert client.put("/api/wishes/chart/standard", json={"item_id": MIST}).status_code == 404
        assert client.put("/api/wishes/chart/weapon", json={"item_id": 1}).status_code == 400
        body = client.put("/api/wishes/chart/weapon", json={"item_id": MIST}).json()
        assert body["fate"]["points"] == 0 and body["fate"]["chart_name"] == "Mistsplitter Reforged"
        body = client.put("/api/wishes/chart/weapon", json={"item_id": None}).json()
        assert body["fate"]["points"] is None


def test_cache_status(paths):
    def reader(game_path):
        raise ImportFailed(ak.NO_WISH_LINK)
    with client_with(paths, reader=reader) as client:
        assert client.get("/api/wishes/cache-status").json() == {"status": "no_link", "cached_at": None}


def test_settings_game_install_path(paths):
    with client_with(paths) as client:
        assert client.get("/api/settings").json()["game_install_path"] == ""
        body = client.put("/api/settings", json={"game_install_path": "  D:/Games/Genshin Impact  "}).json()
        assert body["game_install_path"] == "D:/Games/Genshin Impact"
        assert client.put("/api/settings", json={"game_install_path": "x" * 501}).status_code == 422


def test_no_wish_endpoint_leaks_the_authkey(paths, caplog, tmp_path):
    caplog.set_level(logging.DEBUG)
    write_env(paths)
    game_dir, locallow = make_game_install(tmp_path / "game")
    attempts = {"n": 0}
    good = FakeGachaApi(game_rows())

    def factory(link):
        assert link.authkey == FAKE_AUTHKEY                # the real reader found the key...
        attempts["n"] += 1
        if attempts["n"] == 1:
            async def broken(gacha_type, end_id):
                raise RuntimeError(f"GET {wish_url()} failed")
            return broken
        return good.page

    with make_client(paths, wish_link_reader=lambda gp: ak.load_wish_link(gp, locallow),
                     wish_page_factory=factory) as client:
        client.put("/api/settings", json={"game_install_path": str(game_dir)})
        bodies = []
        for _ in range(2):
            bodies.append(client.post("/api/wishes/import/game").text)
            bodies.append(json.dumps(wait_import(client)))
        bodies += [client.get(p).text for p in ("/api/wishes/summary", "/api/wishes", "/api/wishes/export",
                                                 "/api/wishes/cache-status", "/api/settings", "/api/dashboard")]
    files = [f.read_bytes().decode("utf-8", "replace") for f in paths.wish_backups.glob("uigf-*.json")]
    dbs = [paths.db_file.read_bytes().decode("latin-1")] + [
        f.read_bytes().decode("latin-1") for f in paths.wish_backups.glob("tracker-*.db")]
    for text in [*bodies, caplog.text, *files, *dbs]:
        assert "SECRET-AUTHKEY" not in text and "authkey=" not in text
