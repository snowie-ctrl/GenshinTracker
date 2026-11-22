import logging
import time

from app.db.models import CharacterGoal
from app.settings.envfile import read_env
from app.sync.hoyolab import Account, HoyolabError
from fakes import FakeSource
from app.timeutil import utcnow
from helpers import make_client, seed_game, wait_for_sync, yatta_transport

ACCOUNT = Account(uid=800000001, server="os_usa", nickname="TestTraveler", level=60)
OTHER = Account(uid=800000002, server="os_euro", nickname="Alt", level=20)
COOKIES = {"ltuid_v2": "SECRET-LTUID-111", "ltoken_v2": "SECRET-LTOKEN-222", "ltmid_v2": "SECRET-LTMID-333"}
SECRETS = list(COOKIES.values())


def test_settings_defaults(paths):
    with make_client(paths) as client:
        body = client.get("/api/settings").json()
    assert body["connection"] == {"status": "missing", "uid": None}
    assert body["sync_interval_minutes"] == 10
    assert body["default_targets"] == {"level": 90, "normal": 8, "skill": 8, "burst": 8, "weapon_level": 90}
    assert body["level_caps"] == [20, 40, 50, 60, 70, 80, 90]
    assert body["gamedata"] == {"fetched_at": None, "last_error": None, "count": 0,
                               "materials": {"fetched_at": None, "last_error": None, "count": 0},
                               "banners": {"fetched_at": None, "last_error": None, "count": 0,
                                           "unmapped": []}}


def test_put_settings_validates_and_saves(paths):
    with make_client(paths) as client:
        assert client.put("/api/settings", json={"sync_interval_minutes": 0}).status_code == 422
        bad_targets = {"level": 90, "normal": 11, "skill": 8, "burst": 8, "weapon_level": 90}
        assert client.put("/api/settings", json={"default_targets": bad_targets}).status_code == 422
        good = {"level": 80, "normal": 6, "skill": 6, "burst": 6, "weapon_level": 80}
        body = client.put("/api/settings", json={"sync_interval_minutes": 30, "default_targets": good}).json()
    assert body["sync_interval_minutes"] == 30 and body["default_targets"] == good


def test_connect_single_account_writes_env_and_syncs(paths):
    source = FakeSource()  # roster ids missing from game data are fine here
    with make_client(paths, source=source, accounts=[ACCOUNT]) as client:
        r = client.post("/api/settings/hoyolab", json=COOKIES)
        assert r.status_code == 200
        assert r.json() == {"status": "connected", "uid": 800000001}
        status = wait_for_sync(client)
        settings = client.get("/api/settings").json()
    env = read_env(paths.env_file)
    assert env["LTOKEN_V2"] == "SECRET-LTOKEN-222"
    assert env["GENSHIN_UID"] == "800000001" and env["GENSHIN_REGION"] == "os_usa"
    assert status["runs"][0]["trigger"] == "connect"
    assert settings["connection"] == {"status": "connected", "uid": 800000001}


def test_connect_multiple_accounts_asks_then_accepts_choice(paths):
    with make_client(paths, source=FakeSource(), accounts=[ACCOUNT, OTHER]) as client:
        r = client.post("/api/settings/hoyolab", json=COOKIES)
        assert r.json()["status"] == "choose"
        assert [a["uid"] for a in r.json()["accounts"]] == [800000001, 800000002]
        assert not paths.env_file.exists()
        r = client.post("/api/settings/hoyolab", json={**COOKIES, "uid": 800000002})
        assert r.json() == {"status": "connected", "uid": 800000002}
        wait_for_sync(client)
    assert read_env(paths.env_file)["GENSHIN_REGION"] == "os_euro"


def test_connect_failure_writes_nothing(paths, caplog):
    caplog.set_level(logging.DEBUG)
    with make_client(paths, accounts=HoyolabError("Please login")) as client:
        r = client.post("/api/settings/hoyolab", json=COOKIES)
    assert r.status_code == 400 and "Please login" in r.json()["detail"]
    assert not paths.env_file.exists()
    assert not any(secret in caplog.text for secret in SECRETS)


def test_connect_requires_ltuid_and_ltoken(paths):
    with make_client(paths, accounts=[ACCOUNT]) as client:
        r = client.post("/api/settings/hoyolab", json={"ltuid_v2": "  ", "ltoken_v2": "x"})
    assert r.status_code == 400


def test_connect_cleans_pasted_values(paths):
    messy = {"ltuid_v2": ' "SECRET-LTUID-111" ', "ltoken_v2": "ltoken_v2=SECRET-LTOKEN-222;",
             "ltmid_v2": "'SECRET-LTMID-333'"}
    with make_client(paths, source=FakeSource(), accounts=[ACCOUNT]) as client:
        assert client.post("/api/settings/hoyolab", json=messy).status_code == 200
        wait_for_sync(client)
    env = read_env(paths.env_file)
    assert (env["LTUID_V2"], env["LTOKEN_V2"], env["LTMID_V2"]) == tuple(SECRETS)


import pytest  # noqa: E402

from app.api.settings import HoyolabIn  # noqa: E402


@pytest.mark.parametrize(
    "pasted",
    ['"abc;"', 'abc;"', '"ltoken_v2=abc"', "LTOKEN_V2=abc", "ltoken_v2 = abc", " 'abc' ; ", "abc"],
)
def test_cookie_cleaning_handles_wrapped_quotes_and_prefixes(pasted):
    assert HoyolabIn(ltuid_v2="1", ltoken_v2=pasted).ltoken_v2 == "abc"


def test_connect_clears_stale_optional_keys(paths):
    paths.env_file.write_text("PORT=9000\nCOOKIE_TOKEN_V2=old-token\n", encoding="utf-8")
    with make_client(paths, source=FakeSource(), accounts=[ACCOUNT]) as client:
        client.post("/api/settings/hoyolab", json=COOKIES)
        wait_for_sync(client)
    env = read_env(paths.env_file)
    assert "COOKIE_TOKEN_V2" not in env and env["PORT"] == "9000"


def test_no_endpoint_leaks_cookie_values(paths, caplog):
    caplog.set_level(logging.DEBUG)
    sf = _sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:   # a Build goal, so the sync's gaps part does real calculator work
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=utcnow()))
    source = FakeSource()
    with make_client(paths, source=source, accounts=[ACCOUNT]) as client:
        client.post("/api/settings/hoyolab", json=COOKIES)
        status = wait_for_sync(client)
        assert status["runs"][0]["parts"]["gaps"] == {"ok": True, "count": 1}
        sync = client.app.state.ctx.sync
        sync._gaps_delay = 0.01
        bodies = [
            client.put("/api/characters/10000032/goal",
                       json={"targets": {"level": 90, "normal": 9, "skill": 8, "burst": 8,
                                         "weapon_level": 90}}).text,
            client.put("/api/weekly-bosses/Stormterror", json={"done": True}).text,
        ]
        bodies += [
            client.post("/api/teams", json={"name": "Leak check", "notes": "", "tag_ids": [1], "new_tags": ["abyss"],
                                            "members": [{"character_id": 10000032, "role": ""}]}).text,
            client.get("/api/tags").text,
        ]
        deadline = time.monotonic() + 5
        while sync.gaps_pending or sync.running:          # let the scheduled gaps-only run finish too
            assert time.monotonic() < deadline, "gaps run never finished"
            time.sleep(0.02)
        bodies += [client.get(p).text for p in
                   ("/api/settings", "/api/sync/status", "/api/characters", "/api/dashboard",
                    "/api/inventory", "/api/weapons?type=Sword", "/api/characters/bennett", "/api/teams",
                    "/api/events", "/api/banners/history?pool=character", "/api/profile", "/api/map")]
    assert sum(1 for c in source.calls if isinstance(c, tuple) and c[0] == "gaps") == 2
    for text in [*bodies, caplog.text]:
        assert not any(secret in text for secret in SECRETS)


def test_manual_sync_rate_limit_and_not_connected(paths):
    with make_client(paths, source=None) as client:
        assert client.post("/api/sync?trigger=manual").json()["reason"] == "not_connected"
    with make_client(paths, source=FakeSource()) as client:
        assert client.post("/api/sync?trigger=manual").json()["started"] is True
        wait_for_sync(client)
        r = client.post("/api/sync?trigger=manual")
        assert r.status_code == 429 and "Retry-After" in r.headers


def test_gamedata_refresh_endpoint(paths):
    with make_client(paths, transport=yatta_transport()) as client:
        body = client.post("/api/gamedata/refresh").json()
    assert body["refreshed"] is True and body["gamedata"]["count"] == 6
    assert body["gamedata"]["materials"]["count"] > 0


def _sf_for(paths):
    from app.db.engine import make_engine, make_session_factory, migrate
    engine = make_engine(paths.db_file)
    migrate(engine)
    return make_session_factory(engine)
