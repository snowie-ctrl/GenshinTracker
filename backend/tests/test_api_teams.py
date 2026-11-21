from datetime import datetime

from sqlalchemy import delete

from app.db.models import GapRun, OwnedArtifact
from app.planner.requests import snapshot
from test_api_planner import setup                  # Bennett owned + Build, catalogue, totals, gaps
from helpers import make_client

BEN, FUR, XL, NAH = 10000032, 10000089, 10000023, 10000073


def mark_calculated(sf):
    """Record a successful gap run whose snapshot matches the current goals, so Build members count as calculated."""
    with sf.begin() as s:
        s.merge(GapRun(id=1, ok=True, error=None, skipped=[], computed_at=datetime(2026, 11, 21), snapshot=snapshot(s)))


def body(members=(BEN,), tags=(), new_tags=(), name="Abyss Pyro", notes="", roles=None):
    roles = roles or {}
    return {"name": name, "notes": notes, "members": [{"character_id": c, "role": roles.get(c, "")} for c in members],
            "tag_ids": list(tags), "new_tags": list(new_tags)}


def test_create_list_get_update_delete(paths):
    sf = setup(paths)
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
        assert created["raised"] == []
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
        assert client.delete(f"/api/teams/{team['id']}").status_code == 200
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
    setup(paths)
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


def test_character_detail_and_dashboard(paths):
    sf = setup(paths)
    mark_calculated(sf)
    with make_client(paths) as client:
        tid = client.post("/api/teams", json=body(members=(BEN,), tags=(1,), name="Pyro")).json()["team"]["id"]
        client.post("/api/teams", json=body(members=(XL,), name="Fun"))
        detail = client.get("/api/characters/bennett").json()
        assert [t["name"] for t in detail["teams"]] == ["Pyro"]
        assert client.get("/api/characters/xiangling").json()["teams"] == [
            {"id": tid + 1, "name": "Fun", "tags": []}]
        cards = client.get("/api/dashboard").json()["build_teams"]
    assert [c["name"] for c in cards] == ["Pyro"]
    card = cards[0]
    assert [m["id"] for m in card["members"]] == [BEN]
    assert [(m["id"], m["to_farm"]) for m in card["top"]] == [(104302, 4), (113003, 2)]   # most missing first
    assert card["has_shortfall"] is True and card["more"] == 0


def test_dashboard_card_calculation_flags(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        client.post("/api/teams", json=body(members=(BEN,), tags=(1,), name="Pyro"))
        card = client.get("/api/dashboard").json()["build_teams"][0]
        assert card["all_calculated"] is False and card["short_count"] == 0 and card["top"] == []
        mark_calculated(sf)
        card = client.get("/api/dashboard").json()["build_teams"][0]
    assert card["all_calculated"] is True and card["short_count"] == 2
