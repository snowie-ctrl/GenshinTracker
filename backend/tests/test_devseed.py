from app.config import Paths
from app.devseed import seed
from helpers import make_client


def test_devseed_creates_expected_statuses(tmp_path):
    seed(tmp_path)
    seed(tmp_path)  # re-seeding starts fresh
    paths = Paths(tmp_path)
    with make_client(paths) as client:
        chars = {c["slug"]: c for c in client.get("/api/characters").json()}
        dash = client.get("/api/dashboard").json()
    statuses = {slug: (c["status"], c["prefarming"]) for slug, c in chars.items()}
    assert statuses == {
        "bennett": ("building", False), "furina": ("building", False),
        "xiangling": ("obtained", False), "nahida": ("obtained", False),
        "kazuha": ("wanted", False), "neuvillette": ("wanted", True),
        "raiden-shogun": ("unobtained", False), "xingqiu": ("unobtained", False),
    }
    assert dash["notes"]["resin"] == 120


def test_devseed_contains_planner_data(tmp_path):
    from fastapi.testclient import TestClient

    from app.devseed import seed
    from app.main import create_app
    from app.config import Paths

    seed(tmp_path)
    with TestClient(create_app(Paths(tmp_path), offline=True)) as client:
        dash = client.get("/api/dashboard").json()
        inv = client.get("/api/inventory").json()
    assert dash["farm_today"]["domains"][0]["name"] == "Domain of Mastery: Forsaken Rift"
    assert dash["weekly_bosses"]["bosses"][0]["name"] == "Stormterror"
    assert dash["gaps"]["stale"] is False
    cards = {c["character"]["slug"]: c for c in dash["building_cards"]}
    assert all(c["calculated"] for c in cards.values())
    assert cards["neuvillette"]["materials"] == []          # Build, no rows, in snapshot -> fully built
    states = {m["id"]: m["state"] for c in inv["categories"] for m in c["materials"]}
    assert states[104302] == "short" and states[104003] == "met" and states[100055] == "unneeded"


def test_devseed_wishes(tmp_path):
    from app.config import Paths
    from app.db.engine import make_engine, make_session_factory
    from app.devseed import seed
    from app.timeutil import utcnow
    from app.wishes.pity import summarize

    seed(tmp_path)
    engine = make_engine(Paths(tmp_path).db_file)
    with make_session_factory(engine)() as s:
        r = summarize(s, utcnow(), 8)
    engine.dispose()
    assert (r["character"].total, r["character"].pity5, r["character"].next_state) == (30, 2, "50/50")
    assert [p.outcome for p in r["character"].fives] == ["lost", "guaranteed"]
    assert (r["weapon"].total, r["weapon"].pity5) == (12, 12)
    assert [c["name"] for c in r["weapon"].fate["choices"]] == ["Mistsplitter Reforged", "A Thousand Floating Dreams"]
    assert (r["standard"].total, r["standard"].pity5) == (60, 15)


def test_devseed_teams(tmp_path):
    seed(tmp_path)
    with make_client(Paths(tmp_path)) as client:
        teams = client.get("/api/teams").json()["teams"]
        tags = client.get("/api/tags").json()
    assert [t["name"] for t in teams] == ["Abyss Furina", "Archons only"]
    abyss = teams[0]
    assert [t["name"] for t in abyss["tags"]] == ["Build", "abyss"]
    assert [m["slug"] for m in abyss["members"]] == ["furina", "bennett", "xingqiu"]
    assert [m["not_building"] for m in abyss["members"]] == [False, False, True]
    assert abyss["shortfall"] and teams[1]["tags"] == []
    assert [(t["name"], t["team_count"]) for t in tags] == [("Build", 1), ("abyss", 1)]
