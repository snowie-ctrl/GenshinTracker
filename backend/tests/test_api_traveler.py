from app.db.models import OwnedCharacter, TravelerElement
from app.sync.persist import save_details, save_roster
from app.timeutil import utcnow
from fakes import make_detail, make_roster
from helpers import make_client, seed_game
from test_api_characters import sf_for

CRYO, ANEMO = 1000000507, 1000000502


def synced(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        save_roster(s, [make_roster(CRYO, raw_id=10000007, name="Traveler", element="Cryo")], utcnow())
        save_details(s, [make_detail(CRYO, talents=(4, 9, 10))])
    return sf


def test_detail_has_traveler_block(paths):
    synced(paths)
    with make_client(paths) as c:
        t = c.get("/api/characters/cryo-traveler").json()["traveler"]
        assert t == {"element_id": CRYO, "current": True, "seen": True, "unlocked": False,
                     "talents": {"normal": 4, "skill": 9, "burst": 10}, "constellation": 2, "source": "sync"}
        assert c.get("/api/characters/bennett").json()["traveler"] is None
        anemo = c.get("/api/characters/anemo-traveler").json()
        assert anemo["owned"] is False and anemo["traveler"]["unlocked"] is False


def test_unlock_and_edit_other_element(paths):
    sf = synced(paths)
    with make_client(paths) as c:
        r = c.put(f"/api/traveler/{ANEMO}", json={"unlocked": True, "talents": {"normal": 2, "skill": 6, "burst": 6},
                                                  "constellation": 1})
        assert r.status_code == 200 and r.json()["source"] == "manual"
        a = c.get("/api/characters/anemo-traveler").json()
        assert a["owned"] is True and a["talents"] == {"normal": 2, "skill": 6, "burst": 6} and a["constellation"] == 1
        assert a["level"] == 80
    with sf() as s:
        assert s.get(OwnedCharacter, ANEMO) is not None


def test_errors(paths):
    synced(paths)
    with make_client(paths) as c:
        assert c.put("/api/traveler/10000032", json={"unlocked": True}).status_code == 404
        assert c.put(f"/api/traveler/{CRYO}", json={"constellation": 3}).status_code == 409
        assert c.put(f"/api/traveler/{CRYO}", json={"unlocked": False}).status_code == 409
        assert c.put(f"/api/traveler/{ANEMO}", json={"constellation": 7}).status_code == 422
        assert c.put(f"/api/traveler/{ANEMO}", json={"talents": {"normal": 0, "skill": 1, "burst": 1}}).status_code == 422


def test_unlock_before_any_sync_saves_flag_only(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with make_client(paths) as c:
        r = c.put(f"/api/traveler/{ANEMO}", json={"unlocked": True})
        assert r.status_code == 200 and r.json()["unlocked"] is True and r.json()["current"] is False
        assert c.get("/api/characters/anemo-traveler").json()["owned"] is False   # needs a sync for level/weapon
    with sf() as s:
        assert s.get(TravelerElement, ANEMO).unlocked is True
