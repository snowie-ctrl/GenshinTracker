from datetime import datetime

from app.db.models import GameBanner, Wish
from app.wishes.analysis import (ItemInfo, Phase, analyze, expected_for, expected_pity, load_phases, luck,
                                 primogem_series, rotations, spiders)
from app.wishes.pity import BannerWindow, PullView, banner_windows, summarize_pool
from app.wishes.types import PityRule

FURINA, NAHIDA, MIST, FAV = 10000089, 10000073, 11509, 11401
ITEMS = {FURINA: ItemInfo("Furina", "UI_AvatarIcon_Furina", 5, "Hydro", "Sword"),
         NAHIDA: ItemInfo("Nahida", "UI_AvatarIcon_Nahida", 5, "Dendro", "Catalyst"),
         MIST: ItemInfo("Mistsplitter Reforged", "UI_EquipIcon_Sword_Narukami", 5, None, "Sword"),
         FAV: ItemInfo("Favonius Sword", "UI_EquipIcon_Sword_Zephyrus", 4, None, "Sword")}


def pv(pity, outcome=None, item_id=FURINA, rarity=5, time="2024-01-15 10:00:00", pk=1):
    return PullView(pk, "x", item_id, "character", rarity, time, pity, outcome, None, None)


def test_expected_for_small_rule_and_real_pools():
    assert expected_for(PityRule(2, None, 10), 0.5, 0.0) == 1.5
    assert expected_pity("character") == 62.3
    assert expected_pity("standard") == 62.3
    assert expected_pity("weapon") == 53.3


def test_luck_verdicts_and_record():
    judged = [pv(80, "lost"), pv(10, "guaranteed"), pv(60, "won"), pv(70, "unknown")]
    out = luck(judged, judged, 62.3, "50/50")
    assert out == {"avg_pity": 55.0, "expected": 62.3, "verdict": "luckier", "won": 1, "lost": 1, "rate": 0.5,
                   "judged_label": "50/50"}
    assert luck([pv(62)], [], 62.3, None)["verdict"] == "average"
    assert luck([pv(65)], [], 62.0, None)["verdict"] == "average"            # exactly +3 is still average
    assert luck([pv(66)], [], 62.3, None)["verdict"] == "unluckier"
    assert luck([pv(59)], [], 62.0, None)["verdict"] == "average"            # exactly −3 is still average
    std = luck([pv(66)], [], 62.3, None)
    assert (std["won"], std["lost"], std["rate"], std["judged_label"]) == (None, None, None, None)


def test_luck_without_fives():
    out = luck([], [], 53.3, "75/25")
    assert out == {"avg_pity": None, "expected": 53.3, "verdict": None, "won": 0, "lost": 0, "rate": None,
                   "judged_label": "75/25"}


def test_spiders_counts_zero_fill_and_unknown():
    pulls = [pv(70, item_id=FURINA), pv(50, item_id=NAHIDA), pv(40, item_id=MIST), pv(9, item_id=FAV, rarity=4),
             pv(9, item_id=999999, rarity=4), pv(1, item_id=None, rarity=3)]
    elements, weapons, unknown = spiders(pulls, ITEMS)
    assert elements["five"] == {"Pyro": 0, "Hydro": 1, "Anemo": 0, "Electro": 0, "Dendro": 1, "Cryo": 0, "Geo": 0}
    assert sum(elements["four"].values()) == 0                        # weapons have no element
    assert weapons["five"] == {"Sword": 2, "Claymore": 0, "Polearm": 0, "Bow": 0, "Catalyst": 1}
    assert weapons["four"]["Sword"] == 1
    assert unknown == 1                                                # 3★ never counted, unknown 4★ is


def wish(pk, pool, time, rarity=3, item_id=None, name="Filler"):
    return Wish(pk=pk, id=None, pool=pool, gacha_type={"character": "301", "weapon": "302", "standard": "200"}[pool],
                time=time, seq=0, name=name, item_id=item_id, item_type="character", rarity=rarity, source="game",
                imported_at=datetime(2024, 1, 1))


def window(start, version, pool="character", order=0, end="2099-01-01 00:00:00"):
    return BannerWindow(f"{pool}|{start}|{order}", pool, "B", "B", start, end, order, (FURINA,), (), version)


def test_load_phases_labels_and_dedupes():
    ws = [window("2024-01-10 06:00:00", "4.3"), window("2024-01-10 06:00:00", "4.3", order=1),
          window("2024-01-31 18:00:00", "4.3"), window("2024-02-20 06:00:00", "4.4"),
          window("2024-01-01 00:00:00", None), window("2024-01-12 00:00:00", "4.3", pool="weapon")]
    E = "2099-01-01 00:00:00"
    assert load_phases(ws) == [Phase("4.3 ph1", "4.3", "2024-01-10 06:00:00", E),
                               Phase("4.3 ph2", "4.3", "2024-01-31 18:00:00", E),
                               Phase("4.4 ph1", "4.4", "2024-02-20 06:00:00", E)]


def test_load_phases_end_is_latest_window_end():
    ws = [window("2024-01-10 06:00:00", "4.3", end="2024-01-31 17:59:59"),
          window("2024-01-10 06:00:00", "4.3", order=1, end="2024-01-30 00:00:00")]
    assert load_phases(ws)[0].end == "2024-01-31 17:59:59"


def test_rotations_leave_out_pulls_after_the_last_end_and_in_gaps():
    phases = [Phase("4.3 ph1", "4.3", "2024-01-10 06:00:00", "2024-01-20 00:00:00"),
              Phase("4.3 ph2", "4.3", "2024-02-01 00:00:00", "2024-02-10 00:00:00")]
    rows = [wish(1, "standard", "2024-01-15 10:00:00"),
            wish(2, "standard", "2024-01-25 10:00:00"),                      # gap: left out
            wish(3, "standard", "2024-02-05 10:00:00"),
            wish(4, "standard", "2024-02-20 10:00:00")]                      # after the last end: left out
    out = rotations(rows, phases, ITEMS)
    assert [(e["label"], e["pulls"]) for e in out] == [("4.3 ph1", 1), ("4.3 ph2", 1)]


def test_rotations_bucket_every_pool_and_skip_early_pulls():
    E = "2099-01-01 00:00:00"
    phases = [Phase("4.3 ph1", "4.3", "2024-01-10 06:00:00", E), Phase("4.3 ph2", "4.3", "2024-01-31 18:00:00", E)]
    rows = [wish(1, "standard", "2024-01-09 10:00:00"),                       # before the first phase: left out
            wish(2, "character", "2024-01-11 10:00:00", 5, FURINA, "Furina"),
            wish(3, "standard", "2024-01-20 10:00:00"),
            wish(4, "weapon", "2024-02-01 10:00:00")]
    out = rotations(rows, phases, ITEMS)
    assert out == [
        {"label": "4.3 ph1", "version": "4.3", "start": "2024-01-10 06:00:00",
         "pool_counts": {"character": 1, "standard": 1}, "pulls": 2,
         "fives": [{"name": "Furina", "icon": "UI_AvatarIcon_Furina"}]},
        {"label": "4.3 ph2", "version": "4.3", "start": "2024-01-31 18:00:00",
         "pool_counts": {"weapon": 1}, "pulls": 1, "fives": []}]


def test_primogem_series_one_point_per_day_with_five_marks():
    rows = [wish(1, "character", "2024-01-11 10:00:00"), wish(2, "character", "2024-01-11 11:00:00", 5, FURINA, "Furina"),
            wish(3, "standard", "2024-01-13 09:00:00")]
    assert primogem_series(rows, ITEMS) == {
        "points": [{"date": "2024-01-11", "total": 320}, {"date": "2024-01-13", "total": 480}],
        "fives": [{"date": "2024-01-11", "name": "Furina", "icon": "UI_AvatarIcon_Furina", "total": 320}]}


def run_summary(rows, windows):
    by_pool = {}
    for w in rows:
        by_pool.setdefault(w.pool, []).append(w)
    names = {FURINA: "Furina", NAHIDA: "Nahida", MIST: "Mistsplitter Reforged"}
    from app.wishes.types import POOLS
    return {p: summarize_pool(p, by_pool.get(p, []), [w for w in windows if w.pool == p], None,
                              "2024-02-01 00:00:00", 8, names) for p in POOLS}


def test_analyze_filters_and_blocks():
    windows = [window("2024-01-10 06:00:00", "4.3")]
    rows = ([wish(i, "character", f"2024-01-11 10:{i:02d}:00") for i in range(1, 10)]
            + [wish(10, "character", "2024-01-11 10:10:00", 5, NAHIDA, "Nahida")]                 # lost, pity 10
            + [wish(11, "weapon", "2024-01-12 10:00:00", 4, FAV, "Favonius Sword")]
            + [wish(12, "standard", "2024-01-13 10:00:00")])
    results = run_summary(rows, windows)
    out = analyze(results, rows, load_phases(windows), ITEMS)
    assert set(out) == {"all", "character", "weapon", "standard"}                # chronicled has no pulls
    ch = out["character"]
    assert ch["luck"]["avg_pity"] == 10.0 and ch["luck"]["lost"] == 1 and ch["luck"]["judged_label"] == "50/50"
    assert ch["pity_hist"] == {"buckets": ch["pity_hist"]["buckets"], "soft": 74, "avg": 10.0}
    assert ch["pity_hist"]["buckets"][0] == {"bucket": "1-10", "count": 1}
    assert ch["fives"][0]["name"] == "Nahida" and ch["fives"][0]["pool"] == "character"
    assert ch["fives"][0]["icon"] == "UI_AvatarIcon_Nahida" and ch["fives"][0]["outcome"] == "lost"
    assert ch["elements"]["five"]["Dendro"] == 1 and ch["months"][0]["character"] == 10
    assert out["weapon"]["luck"]["avg_pity"] is None and out["weapon"]["fours"][0]["name"] == "Favonius Sword"
    assert out["standard"]["luck"]["judged_label"] is None
    a = out["all"]
    assert a["luck"]["judged_label"] == "50/50 + 75/25" and a["pity_hist"]["soft"] is None
    assert a["primogems"]["points"][-1]["total"] == 12 * 160
    assert [r["pulls"] for r in a["rotations"]] == [12]
    # pull-weighted expectation: (10 * 62.3 + 1 * 53.3 + 1 * 62.3) / 12 = 61.55 -> 61.5 or 61.6
    assert abs(a["luck"]["expected"] - 61.55) <= 0.051


def test_analyze_without_phases():
    rows = [wish(1, "standard", "2024-01-13 10:00:00")]
    out = analyze(run_summary(rows, []), rows, [], ITEMS)
    assert out["standard"]["rotations"] == [] and out["standard"]["months"][0]["standard"] == 1


def test_banner_windows_carry_version():
    b = GameBanner(key="character|2024-01-10 06:00:00|0", pool="character", name="B", short_name="B",
                   start="2024-01-10 06:00:00", end="2024-01-30 17:59:00", timezone_dependent=False,
                   timezone_dependent_end=False, order=0, featured_5=[], featured_4=[], version="4.3")
    assert banner_windows([b], 8)["character"][0].version == "4.3"
