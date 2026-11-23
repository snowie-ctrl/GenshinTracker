from datetime import datetime

from app.dashboard.view import RESET_KEYS, banners_with_pity, event_list, timers
from app.db.models import LiveNotes
from app.planner.data import CharRef, Domain, Material, PlannerData, Total
from app.planner.inventory import material_index
from app.planner.today import farm_today, weekly_bosses

NOW = datetime(2026, 11, 22, 12, 0, 0)


def notes(**kw):
    base = dict(id=1, resin=100, resin_max=200, resin_full_at=datetime(2026, 11, 22, 20), commissions_done=1,
                commissions_max=4, realm_currency=0, realm_currency_max=2400, expeditions=[], fetched_at=NOW)
    base.update(kw)
    return LiveNotes(**base)


def test_timers_sorted_and_optional_rows():
    rows = timers(notes(realm_currency_full_at=datetime(2026, 11, 23), transformer_ready_at=datetime(2026, 11, 22, 13),
                        expeditions=[{"icon": "https://x/e.png", "finished": False, "return_at": "2026-11-22T14:00:00Z"}]))
    assert [t["kind"] for t in rows] == ["transformer", "expedition", "resin", "realm"]
    assert rows[0]["icon"] == "UI_ItemIcon_220021" and rows[2]["icon"] == "UI_ItemIcon_210"
    assert [t["kind"] for t in timers(notes())] == ["resin"]


def test_event_list_merges_challenge_resets_only():
    events = [{"id": 1, "end": "2026-11-25T04:00:00Z", "done": False},
              {"id": 2, "end": "2026-11-23T04:00:00Z", "done": True}]
    resets = [{"key": "daily", "label": "Daily reset", "at": "2026-11-23T04:00:00Z"},
              {"key": "abyss", "label": "Spiral Abyss", "at": "2026-11-24T04:00:00Z"}]
    out = event_list(events, resets)
    assert [(r["kind"], r.get("id")) for r in out] == [("reset", "reset-abyss"), ("event", 1), ("event", 2)]
    assert out[0]["name"] == "Spiral Abyss" and out[0]["done"] is False
    assert RESET_KEYS == ("abyss", "theater", "stygian")


def test_banners_with_pity_by_pool():
    lines = [{"pool": "character", "pity5": 62, "hard": 90, "next_state": "guaranteed", "fate_points": None}]
    out = banners_with_pity([{"id": 1, "pool": "character"}, {"id": 2, "pool": "weapon"}], lines)
    assert out[0]["pity"]["pity5"] == 62 and out[1]["pity"] is None


def _data():
    mats = {5: Material(5, "Book", "i", 3, "talent", None, [], 1),
            6: Material(6, "Plume", "i", 5, "weekly", None, [{"kind": "weekly_boss", "name": "Stormterror", "days": []}], 2),
            7: Material(7, "Horn", "i", 5, "weekly", None, [{"kind": "weekly_boss", "name": "Andrius", "days": []}], 3)}
    chars = {10: CharRef(10, "Amber", "amber", None), 20: CharRef(20, "Zhongli", "zhongli", None)}
    return PlannerData(materials=mats, totals={5: Total(4, 4, 0), 6: Total(1, 1, 0), 7: Total(1, 1, 0)},
                       gaps={10: {5: (2, 2), 7: (1, 1)}, 20: {5: (2, 2), 6: (1, 1)}}, characters=chars,
                       domains=[Domain(1, "A domain", "talent", 1, [0, 3], [5]),
                                Domain(2, "B domain", "talent", 1, [0, 3], [5])])


def test_ranked_characters_and_cards():
    d = _data()
    idx = material_index(d)
    day = farm_today(d, 0, idx, {20: 0, 10: 1})
    assert [c["name"] for c in day["domains"][0]["characters"]] == ["Zhongli", "Amber"]
    assert [x["name"] for x in day["domains"]] == ["A domain", "B domain"]          # same best rank -> name
    assert farm_today(d, 1, idx, {})["domains"] == []
    assert len(farm_today(d, 6, idx, {})["domains"]) == 2                            # Sunday: all open
    bosses = weekly_bosses(d, {"Stormterror"}, idx, {10: 0, 20: 1})
    assert [b["name"] for b in bosses] == ["Andrius", "Stormterror"]                 # done sinks
    bosses = weekly_bosses(d, set(), idx, {20: 0, 10: 1})
    assert [b["name"] for b in bosses] == ["Stormterror", "Andrius"]                 # Zhongli first
