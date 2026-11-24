from app.db.models import HoyolabSnapshot
from app.timeutil import utcnow
from helpers import make_client
from test_api_planner import sf_for
from test_profile_view import DATA


def test_profile_endpoint(paths):
    sf = sf_for(paths)
    with make_client(paths) as client:
        empty = client.get("/api/profile").json()
        assert empty["profile"] is None and empty["fetched_at"] is None
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="profile", data=DATA, fetched_at=utcnow()))
    with make_client(paths) as client:
        body = client.get("/api/profile").json()
    assert body["profile"]["header"]["ar"] == 60 and body["profile"]["header"]["name"] == "Traveler"
    assert set(body["challenges"]) == {"abyss", "theater", "stygian"}
    assert body["roster"]["total"] == 0


def test_showcase_endpoint(paths):
    from datetime import datetime

    from app.db.models import OwnedCharacter
    sf = sf_for(paths)
    with sf.begin() as s:
        for cid, name in ((10000089, "Furina"), (10000032, "Bennett")):
            s.add(OwnedCharacter(character_id=cid, name=name, element=None, icon=None, level=90, constellation=0,
                                 friendship=10, weapon_name="W", weapon_icon="", weapon_rarity=4, weapon_level=90,
                                 weapon_refinement=1, stats=[], synced_at=datetime(2026, 11, 1)))
    with make_client(paths) as client:
        body = client.get("/api/profile").json()
        assert body["showcase_mode"] == "auto" and [e["name"] for e in body["showcase"]] == ["Bennett", "Furina"]
        assert [o["name"] for o in body["owned"]] == ["Bennett", "Furina"]
        bad = client.put("/api/profile/showcase", json={"ids": [42]})
        assert bad.status_code == 400 and bad.json()["detail"] == "Only characters you own can be shown."
        ok = client.put("/api/profile/showcase", json={"ids": [10000089]}).json()
        assert ok["showcase_mode"] == "custom" and [e["id"] for e in ok["showcase"]] == [10000089]
        assert client.get("/api/profile").json()["showcase_mode"] == "custom"
        reset = client.put("/api/profile/showcase", json={"ids": []}).json()
        assert reset["showcase_mode"] == "auto" and len(reset["showcase"]) == 2
