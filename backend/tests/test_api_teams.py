from datetime import datetime

from sqlalchemy import delete

from app.db.models import GameArtifactSet, GapRun, OwnedArtifact
from app.planner.requests import snapshot
from app.api.teams import team_views
from app.teams.view import build_team_cards
from test_api_planner import setup                  # Bennett owned + Build, catalogue, totals, gaps
from helpers import drop_default_tags, make_client

BEN, FUR, XL, NAH = 10000032, 10000089, 10000023, 10000073


def mark_calculated(sf):
    """Record a successful gap run whose snapshot matches the current goals, so Build members count as calculated."""
    with sf.begin() as s:
        s.merge(GapRun(id=1, ok=True, error=None, skipped=[], computed_at=datetime(2026, 11, 21), snapshot=snapshot(s)))


def team_cards(sf):
    with sf() as s:
        return build_team_cards(team_views(s))


def body(members=(BEN,), tags=(), new_tags=(), name="Abyss Pyro", notes="", roles=None):
    roles = roles or {}
    return {"name": name, "notes": notes, "members": [{"character_id": c, "role": roles.get(c, "")} for c in members],
            "tag_ids": list(tags), "new_tags": list(new_tags)}


def test_create_list_get_update_delete(paths):
    sf = setup(paths)
    drop_default_tags(sf)
    mark_calculated(sf)
    with sf.begin() as s:
        s.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == BEN))
        for slot in range(1, 5):
            s.add(OwnedArtifact(character_id=BEN, slot=slot, set_name="Noblesse Oblige", rarity=5, level=20,
                                main_stat="HP", substats=[], icon=""))
    with make_client(paths) as client:
        r = client.post("/api/teams", json=body(members=(BEN, XL), new_tags=("abyss",), roles={BEN: "battery"}))
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["raised"] == [] and created["lowered"] == []
        team = created["team"]
        assert [t["name"] for t in team["tags"]] == ["abyss"] and team["has_build_tag"] is False
        ben = team["members"][0]
        assert (ben["name"], ben["role"], ben["status"], ben["level"]) == ("Bennett", "battery", "building", 80)
        assert ben["artifact_line"] == "4pc Noblesse Oblige" and ben["not_building"] is False and ben["not_calculated"] is False
        assert team["shortfall"][0]["id"] == 104302           # Bennett is Build, so the team has a shortfall
        listing = client.get("/api/teams").json()
        assert listing["connected"] is False and [t["id"] for t in listing["teams"]] == [team["id"]]
        one = client.get(f"/api/teams/{team['id']}").json()
        assert one["team"]["name"] == "Abyss Pyro" and "gaps" in one
        r = client.put(f"/api/teams/{team['id']}", json=body(members=(XL,), name="Renamed"))
        assert r.json()["team"]["name"] == "Renamed" and r.json()["team"]["shortfall"] is None
        d = client.delete(f"/api/teams/{team['id']}")
        assert d.status_code == 200 and d.json() == {"ok": True, "lowered": []}
        assert client.get(f"/api/teams/{team['id']}").status_code == 404
        assert client.put(f"/api/teams/{team['id']}", json=body()).json()["detail"] == "Team not found"


def test_build_tag_raises_and_schedules_gaps(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        sync = client.app.state.ctx.sync
        r = client.post("/api/teams", json=body(members=(BEN, NAH), tags=(1,))).json()
        assert r["raised"] == [NAH]
        assert sync.gaps_pending                               # a gaps-only run was scheduled
        assert r["team"]["has_build_tag"] is True
        chars = {c["id"]: c for c in client.get("/api/characters").json()}
        assert chars[NAH]["goal"] == "build" and chars[NAH]["team_tags"] == [[1]]
        assert chars[XL]["team_tags"] == []


def test_newly_raised_member_is_not_calculated(paths):
    sf = setup(paths)
    mark_calculated(sf)                                        # Bennett calculated; Nahida not yet
    with make_client(paths) as client:
        team = client.post("/api/teams", json=body(members=(BEN, NAH), tags=(1,))).json()["team"]
    flags = {m["id"]: m["not_calculated"] for m in team["members"]}
    assert flags == {BEN: False, NAH: True}
    assert {r["id"] for r in team["shortfall"]} == {104302, 113003}   # from Bennett only


def test_not_building_badge(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        tid = client.post("/api/teams", json=body(members=(BEN, NAH), tags=(1,))).json()["team"]["id"]
        client.put(f"/api/characters/{NAH}/goal", json={"goal": "want"})
        team = client.get(f"/api/teams/{tid}").json()["team"]
    assert {m["id"]: m["not_building"] for m in team["members"]} == {BEN: False, NAH: True}


def test_validation_errors(paths):
    setup(paths)
    with make_client(paths) as client:
        assert client.post("/api/teams", json=body(members=())).json()["detail"] == "A team needs 1 to 4 members"
        assert client.post("/api/teams", json=body(members=(BEN, BEN))).status_code == 422
        assert client.post("/api/teams", json=body(name="")).status_code == 422
        assert client.post("/api/teams", json={"name": "x"}).status_code == 422   # members missing
        assert client.get("/api/teams").json()["teams"] == []


def test_reorder_endpoint(paths):
    setup(paths)
    with make_client(paths) as client:
        a = client.post("/api/teams", json=body(name="A")).json()["team"]["id"]
        b = client.post("/api/teams", json=body(name="B")).json()["team"]["id"]
        assert [t["name"] for t in client.get("/api/teams").json()["teams"]] == ["B", "A"]
        assert client.put("/api/teams/order", json={"ids": [a, b]}).status_code == 200
        assert [t["name"] for t in client.get("/api/teams").json()["teams"]] == ["A", "B"]
        client.delete(f"/api/teams/{b}")
        r = client.put("/api/teams/order", json={"ids": [a, b]})
        assert (r.status_code, r.json()["detail"]) == (422, "The order must list every team once")


def test_tag_endpoints(paths):
    sf = setup(paths)
    drop_default_tags(sf)
    with make_client(paths) as client:
        fun = client.post("/api/tags", json={"name": "fun"}).json()
        assert client.post("/api/tags", json={"name": "FUN"}).status_code == 409
        assert client.put(f"/api/tags/{fun['id']}", json={"name": "party", "color": "pink"}).json()["color"] == "pink"
        assert client.put("/api/tags/1", json={"name": "Farm"}).json()["detail"] == "Build is a built-in tag"
        assert client.delete("/api/tags/1").status_code == 409
        client.post("/api/teams", json=body(tags=(fun["id"],)))
        tags = client.get("/api/tags").json()
        assert [(t["name"], t["team_count"]) for t in tags] == [("Build", 0), ("party", 1)]
        assert client.delete(f"/api/tags/{fun['id']}").status_code == 200
        assert client.delete(f"/api/tags/{fun['id']}").status_code == 404


def test_character_detail_and_build_team_cards(paths):
    sf = setup(paths)
    mark_calculated(sf)
    with make_client(paths) as client:
        tid = client.post("/api/teams", json=body(members=(BEN,), tags=(1,), name="Pyro")).json()["team"]["id"]
        client.post("/api/teams", json=body(members=(XL,), name="Fun"))
        detail = client.get("/api/characters/bennett").json()
        assert [t["name"] for t in detail["teams"]] == ["Pyro"]
        assert client.get("/api/characters/xiangling").json()["teams"] == [
            {"id": tid + 1, "name": "Fun", "tags": []}]
        cards = team_cards(sf)
    assert [c["name"] for c in cards] == ["Pyro"]
    card = cards[0]
    assert [m["id"] for m in card["members"]] == [BEN]
    assert [(m["id"], m["to_farm"]) for m in card["top"]] == [(104302, 4), (113003, 2)]   # most missing first
    assert card["has_shortfall"] is True and card["more"] == 0


def test_build_team_card_calculation_flags(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        client.post("/api/teams", json=body(members=(BEN,), tags=(1,), name="Pyro"))
        card = team_cards(sf)[0]
        assert card["all_calculated"] is False and card["short_count"] == 0 and card["top"] == []
        mark_calculated(sf)
        card = team_cards(sf)[0]
    assert card["all_calculated"] is True and card["short_count"] == 2


def test_member_payload_has_art_constellation_and_sets(paths):
    sf = setup(paths)
    drop_default_tags(sf)
    with sf.begin() as s:
        s.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == BEN))
        s.merge(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=0))
        for slot in range(1, 5):
            s.add(OwnedArtifact(character_id=BEN, slot=slot, set_name="Noblesse Oblige", rarity=5, level=20,
                                main_stat="HP", substats=[], icon=""))
    with make_client(paths) as client:
        team = client.post("/api/teams", json=body(members=(BEN, XL))).json()["team"]
    ben, xl = team["members"]
    assert ben["artifact_sets"] == [{"name": "Noblesse Oblige", "icon": "UI_RelicIcon_15007_4", "pieces": 4}]
    assert ben["splash"].startswith("UI_Gacha_AvatarImg_") and isinstance(ben["constellation"], int)
    assert xl["artifact_sets"] == [] and xl["constellation"] is None


def test_build_endpoint_on_off_and_lowered_in_responses(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        sync = client.app.state.ctx.sync
        tid = client.post("/api/teams", json=body(members=(BEN, NAH))).json()["team"]["id"]
        on = client.put(f"/api/teams/{tid}/build", json={"on": True}).json()
        assert on["raised"] == [NAH] and on["lowered"] == [] and on["team"]["has_build_tag"] is True
        assert sync.gaps_pending
        off = client.put(f"/api/teams/{tid}/build", json={"on": False}).json()
        assert off["raised"] == [] and set(off["lowered"]) == {BEN, NAH}
        chars = {c["id"]: c for c in client.get("/api/characters").json()}
        assert chars[NAH]["goal"] == "none" and chars[BEN]["goal"] == "none"
        client.put(f"/api/teams/{tid}/build", json={"on": True})
        r = client.put(f"/api/teams/{tid}", json=body(members=(BEN,), tags=(1,))).json()
        assert r["lowered"] == [NAH] and r["raised"] == []
        d = client.delete(f"/api/teams/{tid}").json()
        assert d == {"ok": True, "lowered": [BEN]}


def test_build_endpoint_noop(paths):
    setup(paths)
    with make_client(paths) as client:
        tid = client.post("/api/teams", json=body(members=(XL,))).json()["team"]["id"]
        r = client.put(f"/api/teams/{tid}/build", json={"on": False}).json()
        assert (r["raised"], r["lowered"]) == ([], [])
        assert client.put("/api/teams/999/build", json={"on": True}).status_code == 404


def test_noop_build_switch_and_noop_save_schedule_no_gaps(paths):
    """Spec §11: gaps are scheduled only when a goal changed."""
    setup(paths)                                               # Bennett is already Build
    with make_client(paths) as client:
        sync = client.app.state.ctx.sync
        built = client.post("/api/teams", json=body(members=(BEN,), tags=(1,))).json()
        assert (built["raised"], built["lowered"]) == ([], []) and not sync.gaps_pending
        tid = built["team"]["id"]
        on = client.put(f"/api/teams/{tid}/build", json={"on": True}).json()        # already on
        assert (on["raised"], on["lowered"]) == ([], []) and not sync.gaps_pending
        plain = client.post("/api/teams", json=body(members=(XL,), name="Plain")).json()["team"]["id"]
        off = client.put(f"/api/teams/{plain}/build", json={"on": False}).json()     # already off
        assert (off["raised"], off["lowered"]) == ([], []) and not sync.gaps_pending
        # Saves that raise and lower nothing: rename + role on the Build team, add a member to a team without Build.
        r = client.put(f"/api/teams/{tid}", json=body(members=(BEN,), tags=(1,), name="Renamed", roles={BEN: "battery"})).json()
        assert (r["raised"], r["lowered"]) == ([], []) and not sync.gaps_pending
        r = client.put(f"/api/teams/{plain}", json=body(members=(XL, NAH), name="Plain")).json()
        assert (r["raised"], r["lowered"]) == ([], []) and not sync.gaps_pending
        # Control: a real change does schedule.
        assert client.put(f"/api/teams/{plain}/build", json={"on": True}).json()["raised"] and sync.gaps_pending
