from datetime import datetime

from app.db.models import ChallengeRun
from app.profile.view import challenge_views, profile_summary, profile_view
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


def test_profile_view():
    v = profile_view(DATA)
    assert (v["ar"], v["days_active"]) == (60, 1200)
    assert {"label": "Achievements", "value": 900} in v["tiles"]
    assert v["chests"][0] == {"label": "Common", "value": 3000}
    assert {"label": "Cryoculi", "value": 0} not in v["oculi"]          # zero oculi types hidden
    assert v["regions"][0]["name"] == "Mondstadt"
    assert profile_view(None) is None


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
        summary = profile_summary(s, NOW)
    assert v["abyss"]["current"]["season"] == "101"
    assert v["abyss"]["current"]["teams"][0][0]["name"] == "Furina"
    assert [r["season"] for r in v["abyss"]["past"]] == ["100", "99"]
    assert v["theater"]["current"] is None and v["theater"]["past"][0]["season"] == "77"
    assert v["stygian"] == {"current": None, "past": []}
    assert summary == {"ar": None, "fetched_at": None, "abyss_stars": 36, "theater_act": None}
