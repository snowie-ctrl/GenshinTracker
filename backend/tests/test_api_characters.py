from datetime import datetime

import httpx

from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import CharacterGoal, GameCharacter
from app.sync.persist import save_details, save_notes, save_roster
from app.timeutil import utcnow
from fakes import NOTES, make_detail, make_roster
from helpers import make_client, seed_game


def sf_for(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    return make_session_factory(engine)


def setup_data(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        s.add(GameCharacter(id=10000999, name="Futurechar", slug="futurechar", rarity=5, element="Cryo",
                            weapon_type="Catalyst", region=None, icon="UI_AvatarIcon_Futurechar",
                            splash="UI_Gacha_AvatarImg_Futurechar", release_at=datetime(2100, 1, 1)))
        now = utcnow()
        save_roster(s, [make_roster(10000032, level=80, name="Bennett"),
                        make_roster(10000089, level=90, name="Furina"),
                        make_roster(1000000503, raw_id=10000007, name="Traveler", element="Geo")], now)
        save_details(s, [make_detail(10000032, talents=(4, 8, 8)), make_detail(10000089)])
        save_notes(s, NOTES, now)
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=now))
        s.add(CharacterGoal(character_id=10000073, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=now))
    return sf


def by_slug(items):
    return {c["slug"]: c for c in items}


def test_list_statuses_and_visibility(paths):
    setup_data(paths)
    with make_client(paths) as client:
        chars = by_slug(client.get("/api/characters").json())
    assert chars["bennett"]["status"] == "building"
    assert chars["bennett"]["progress"] == round((80 / 90 + 4 / 8 + 1 + 1) / 4, 4)
    assert chars["furina"]["status"] == "obtained" and chars["furina"]["progress"] is None
    assert chars["nahida"]["status"] == "wanted" and chars["nahida"]["prefarming"] is True
    assert chars["xiangling"]["status"] == "unobtained" and chars["xiangling"]["targets"] is None
    assert "futurechar" not in chars  # unreleased, not owned


def test_traveler_uses_variant_icon_and_element(paths):
    setup_data(paths)
    with make_client(paths) as client:
        trav = by_slug(client.get("/api/characters").json())["geo-traveler"]
    assert trav["icon"] == "UI_AvatarIcon_PlayerGirl"
    assert trav["splash"] == "UI_Gacha_AvatarImg_PlayerGirl"
    assert trav["element"] == "Geo"


def test_owned_character_without_game_data_is_placeholder(paths):
    sf = sf_for(paths)
    with sf.begin() as s:
        save_roster(s, [make_roster(10000777, name="Brandnew", element="Hydro")], utcnow())
    with make_client(paths) as client:
        chars = by_slug(client.get("/api/characters").json())
        detail = client.get("/api/characters/id-10000777")
    c = chars["id-10000777"]
    assert (c["name"], c["status"], c["element"], c["icon"], c["rarity"]) == \
        ("Brandnew", "obtained", "Hydro", None, 0)
    assert detail.status_code == 200


def test_detail_includes_artifacts_and_stats(paths):
    setup_data(paths)
    with make_client(paths) as client:
        d = client.get("/api/characters/bennett").json()
        missing = client.get("/api/characters/nobody")
    assert d["artifacts"][0]["set_name"] == "Noblesse Oblige"
    assert d["stats"] == [{"name": "HP", "value": "20000"}]
    assert d["talents"] == {"normal": 4, "skill": 8, "burst": 8}
    assert missing.status_code == 404


def test_set_goal_build_fills_defaults_and_leaving_keeps_targets(paths):
    setup_data(paths)
    with make_client(paths) as client:
        c = client.put("/api/characters/10000089/goal", json={"goal": "build"}).json()
        assert c["status"] == "building"
        assert c["targets"] == {"level": 90, "normal": 8, "skill": 8, "burst": 8, "weapon_level": 90}
        custom = {"level": 80, "normal": 6, "skill": 9, "burst": 9, "weapon_level": 80}
        client.put("/api/characters/10000089/goal", json={"targets": custom})
        c = client.put("/api/characters/10000089/goal", json={"goal": "none"}).json()
        assert c["status"] == "obtained" and c["targets"] == custom
        c = client.put("/api/characters/10000089/goal", json={"goal": "build"}).json()
        assert c["targets"] == custom


def test_set_goal_validation_and_404(paths):
    setup_data(paths)
    with make_client(paths) as client:
        assert client.put("/api/characters/10000089/goal", json={"goal": "maybe"}).status_code == 422
        assert client.put("/api/characters/1/goal", json={"goal": "build"}).status_code == 404


def test_dashboard(paths):
    with make_client(paths) as client:
        empty = client.get("/api/dashboard").json()
    assert empty["notes"] is None and empty["builds"] == []
    setup_data(paths)
    with make_client(paths) as client:
        d = client.get("/api/dashboard").json()
    assert d["notes"]["resin"] == 153 and d["notes"]["resin_full_at"].endswith("Z")
    assert len([b for b in d["builds"] if b["progress"] is not None]) == 1   # Nahida is Build but not owned
    assert d["connection"]["status"] == "missing"


def test_img_routes(paths):
    def handler(request):
        return httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})

    with make_client(paths, transport=httpx.MockTransport(handler)) as client:
        named = client.get("/api/img/UI_AvatarIcon_Bennett")
        bad = client.get("/api/img/..%2Fsecret")
        remote_bad = client.get("/api/img/remote", params={"url": "https://evil.com/a.png"})
    # make_client runs offline=True, so named images come back as the placeholder, uncached
    assert named.status_code == 200 and named.headers["cache-control"] == "no-store"
    assert bad.status_code in (400, 404)
    assert remote_bad.status_code == 400


def test_characters_have_release_date(paths):
    setup_data(paths)
    with make_client(paths) as client:
        chars = client.get("/api/characters").json()
    import re
    assert all(c["release_at"] is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["release_at"]) for c in chars)
    assert any(c["release_at"] for c in chars)
