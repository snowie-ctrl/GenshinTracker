from app.dashboard.artifacts import HINT, group_artifact_domains

SETS = {15007: {"id": 15007, "name": "Noblesse Oblige", "icon": "N"},
        15008: {"id": 15008, "name": "Bloodstained Chivalry", "icon": "B"},
        15001: {"id": 15001, "name": "Gladiator's Finale", "icon": "G"},
        15020: {"id": 15020, "name": "Emblem of Severed Fate", "icon": "E"},
        15019: {"id": 15019, "name": "Shimenawa's Reminiscence", "icon": "S"}}
DOMAINS = [{"id": 5101, "name": "Domain of Blessing: Stone Chamber", "entrance": "Clear Pool and Mountain Cavern",
            "region": "Liyue", "elements": ["Hydro"], "set_ids": [15008, 15007]},
           {"id": 5301, "name": "Domain of Blessing: Autumn Hunt", "entrance": "Momiji-Dyed Court",
            "region": "Inazuma", "elements": ["Electro"], "set_ids": [15020, 15019]}]


def char(cid, name):
    return {"id": cid, "name": name, "slug": name.lower(), "icon": f"UI_{name}"}


def build(cid, name, sets, status="missing", done=False, equipped=None):
    target = {"sets": [{"set_id": sid, "pieces": p} for sid, p in sets], "main": {}, "subs": []} if sets is not None else None
    eq = equipped or {}
    return {"character": char(cid, name), "target": target, "done": done,
            "check": {"status": status, "sets": [{"set_id": sid, "equipped": eq.get(sid, 0)} for sid, _ in (sets or [])]}}


def test_groups_by_domain_in_priority_order():
    builds = [build(1, "Ayaka", [(15020, 4)], equipped={15020: 2}),
              build(2, "Furina", [(15007, 2), (15001, 2)]),
              build(3, "Neuvi", [(15008, 4)])]
    r = group_artifact_domains(builds, SETS, DOMAINS)
    assert [d["entrance"] for d in r["domains"]] == ["Momiji-Dyed Court", "Clear Pool and Mountain Cavern"]
    autumn = r["domains"][0]
    assert [(s["name"], s["needed"]) for s in autumn["sets"]] == [("Emblem of Severed Fate", True),
                                                                 ("Shimenawa's Reminiscence", False)]
    assert autumn["sets"][0]["characters"] == [{**char(1, "Ayaka"), "pieces": 4, "equipped": 2}]
    stone = r["domains"][1]
    assert [c["name"] for c in stone["sets"][0]["characters"]] == ["Neuvi"]     # Bloodstained
    assert [c["name"] for c in stone["sets"][1]["characters"]] == ["Furina"]    # Noblesse
    assert [o["name"] for o in r["other"]] == ["Gladiator's Finale"]
    assert r["other"][0]["characters"][0]["name"] == "Furina" and r["hint"] is None


def test_met_done_and_no_sets_are_not_counted():
    builds = [build(1, "Met", [(15007, 4)], status="met"),
              build(2, "Done", [(15007, 4)], done=True),
              build(3, "Stats", []),
              build(4, "None", None, status="none")]
    r = group_artifact_domains(builds, SETS, DOMAINS)
    assert r == {"domains": [], "other": [], "hint": None}


def test_hint_when_builds_have_no_set_targets():
    r = group_artifact_domains([build(1, "A", None, status="none")], SETS, DOMAINS)
    assert r == {"domains": [], "other": [], "hint": HINT}
    assert group_artifact_domains([], SETS, DOMAINS)["hint"] is None


def test_ties_sort_by_name_and_unknown_set_goes_to_other():
    builds = [build(1, "A", [(15020, 2), (15008, 2)]), build(2, "B", [(77777, 4)])]
    r = group_artifact_domains(builds, SETS, DOMAINS)
    assert [d["name"] for d in r["domains"]] == ["Domain of Blessing: Autumn Hunt", "Domain of Blessing: Stone Chamber"]
    assert r["other"][0]["name"] == "Set 77777" and r["other"][0]["icon"] is None
