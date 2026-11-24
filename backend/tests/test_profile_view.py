from datetime import datetime

from app.db.models import ChallengeRun, OwnedCharacter
from app.profile.view import challenge_views, profile_view, roster_view
from helpers import seed_game

NOW = datetime(2026, 11, 21, 12, 0, 0)
DATA = {"stats": {"ar": 60, "days_active": 1200, "achievements": 900, "characters": 95,
                  "chests": {"common": 3000, "exquisite": 2000, "precious": 600, "luxurious": 200, "remarkable": 100},
                  "oculi": {"anemoculi": 66, "geoculi": 131, "electroculi": 181, "dendroculi": 271,
                            "hydroculi": 271, "pyroculi": 200, "cryoculi": 0, "lunoculi": 0},
                  "waypoints": 400, "domains": 70},
        "regions": [{"id": 1, "name": "Mondstadt", "explored": 100.0, "reputation": 8,
                     "offerings": [{"name": "Frostbearing Tree", "level": 12}]}]}


def add_run(s, kind, season, end, summary, teams=()):
    s.add(ChallengeRun(kind=kind, season=season, start="2026-10-16T04:00:00Z", end=end, summary=summary,
                       teams=[list(t) for t in teams], seen_at=NOW, updated_at=NOW))


NEW = {**DATA,
       "stats": {**DATA["stats"], "max_friendship": 40, "abyss": "12-3"},
       "regions": [{"id": 1, "name": "Mondstadt", "explored": 100.0, "reputation": 8, "icon": "https://x.test/m.png",
                    "offerings": [{"name": "Frostbearing Tree", "level": 12, "icon": "https://x.test/t.png"}],
                    "areas": [{"name": "Starfell Valley", "explored": 100.0}],
                    "bosses": [{"name": "Stormterror", "kills": 12}, {"name": "Anemo Hypostasis", "kills": 30}]},
                   {"id": 2, "name": "Liyue", "explored": 90.0, "reputation": 7, "offerings": [],
                    "bosses": [{"name": "Stormterror", "kills": 1}, {"name": "Azhdaha", "kills": 20}]}],
       "teapot": {"level": 10, "comfort": 21400, "comfort_name": "Exquisite", "comfort_icon": "", "items": 312,
                  "visitors": 40, "realms": []}}


def test_profile_view():
    v = profile_view(NEW, "  Lumine  ")
    assert v["header"] == {"name": "Lumine", "ar": 60, "days_active": 1200, "achievements": 900}
    tiles = {t["key"]: t for t in v["tiles"]}
    assert list(tiles) == ["characters", "friendship", "waypoint", "domain", "abyss", "chest", "oculus"]
    assert tiles["friendship"]["value"] == 40 and tiles["abyss"]["value"] == "12-3"
    assert tiles["chest"]["value"] == 5900 and tiles["chest"]["detail"][0] == {"label": "Common", "value": 3000}
    assert {"label": "Cryoculi", "value": 0} not in tiles["oculus"]["detail"]        # zero oculi types hidden
    assert tiles["oculus"]["value"] == 1120
    r = v["regions"][0]
    assert r["icon"] == "https://x.test/m.png" and r["offerings"][0]["icon"] == "https://x.test/t.png"
    assert r["areas"] == [{"name": "Starfell Valley", "explored": 100.0}]
    assert v["regions"][1]["icon"] is None and v["regions"][1]["areas"] == []
    assert v["bosses"] == [{"name": "Anemo Hypostasis", "kills": 30}, {"name": "Azhdaha", "kills": 20},
                           {"name": "Stormterror", "kills": 13}]
    assert v["teapot"]["level"] == 10
    assert profile_view(None) is None


def test_profile_view_old_snapshot():
    v = profile_view(DATA)
    assert v["header"]["name"] == "Traveler"
    assert [t["key"] for t in v["tiles"]] == ["characters", "waypoint", "domain", "chest", "oculus"]
    assert v["teapot"] is None and v["bosses"] == []
    assert v["regions"][0]["areas"] == [] and v["regions"][0]["offerings"][0]["icon"] is None


def own(s, cid, name, level=90, cons=0, element=None):
    from datetime import datetime
    s.add(OwnedCharacter(character_id=cid, name=name, element=element, icon=None, level=level, constellation=cons,
                         friendship=10, weapon_name="W", weapon_icon="", weapon_rarity=4, weapon_level=90,
                         weapon_refinement=1, stats=[], synced_at=datetime(2026, 11, 1)))


def test_roster_view(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 10000089, "Furina", cons=6)
        own(s, 10000032, "Bennett", cons=2)
        own(s, 1000000507, "Cryo Traveler", element="Cryo")
        own(s, 424242, "Not In Game Data", element="Geo")
    with session_factory() as s:
        r = roster_view(s)
    assert r["total"] == 4 and r["constellations"] == 8 and r["c6"] == 1
    assert r["elements"]["Hydro"] == 1 and r["elements"]["Pyro"] == 1 and r["elements"]["Cryo"] == 1
    assert r["elements"]["Geo"] == 1                                   # owned row's own element still counts
    assert r["weapon_types"]["Sword"] == 3 and r["rarity"] == {"5": 2, "4": 1}


def test_roster_view_counts_one_traveler(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 10000089, "Furina")
        own(s, 1000000507, "Cryo Traveler", element="Cryo")
        own(s, 1000000502, "Anemo Traveler", element="Anemo")
    with session_factory() as s:
        r = roster_view(s)
    assert r["total"] == 2 and r["rarity"] == {"5": 2, "4": 0}
    assert r["elements"]["Anemo"] == 1 and r["elements"]["Cryo"] == 0   # lowest id kept when none is current
    assert r["weapon_types"]["Sword"] == 2


def test_profile_view_sorts_regions_and_hides_zero_reputation():
    data = {**DATA, "regions": [
        {"id": 9, "name": "Snezhnaya", "explored": 10.0, "reputation": 0, "offerings": []},
        {"id": 2, "name": "Liyue", "explored": 90.0, "reputation": 7, "offerings": []},
        {"id": 5, "name": "Odd", "explored": 1.0, "reputation": -1, "offerings": []},
        {"id": 1, "name": "Mondstadt", "explored": 100.0, "reputation": None, "offerings": []},
    ]}
    regions = profile_view(data)["regions"]
    assert [r["id"] for r in regions] == [1, 2, 5, 9]
    assert [r["reputation"] for r in regions] == [None, 7, None, None]
    assert data["regions"][0]["reputation"] == 0                        # input not mutated


def test_challenge_views_current_and_past(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        add_run(s, "abyss", "101", "2026-12-16T04:00:00Z", {"stars": 36}, [(10000089, 10000032)])
        add_run(s, "abyss", "100", "2026-11-16T04:00:00Z", {"stars": 30})
        add_run(s, "abyss", "99", "2026-10-16T04:00:00Z", {"stars": 27})
        add_run(s, "theater", "77", "2026-11-01T04:00:00Z", {"act": 8})
    with session_factory() as s:
        v = challenge_views(s, NOW)
    assert v["abyss"]["current"]["season"] == "101"
    assert v["abyss"]["current"]["teams"][0][0]["name"] == "Furina"
    assert [r["season"] for r in v["abyss"]["past"]] == ["100", "99"]
    assert v["theater"]["current"] is None and v["theater"]["past"][0]["season"] == "77"
    assert v["stygian"] == {"current": None, "past": []}
