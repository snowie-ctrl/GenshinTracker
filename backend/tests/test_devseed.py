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
    states = {m["id"]: m["state"] for c in inv["categories"] for m in c["materials"]}
    assert states[104302] == "short" and states[104003] == "met" and states[100055] == "unneeded"
