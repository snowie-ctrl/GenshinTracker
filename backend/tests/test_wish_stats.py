from datetime import datetime

from app.db.models import Wish
from app.wishes.pity import BannerWindow, PoolResult, PullView
from app.wishes.stats import banner_timeline, monthly, overall_stats, pity_histogram, pool_stats

B = BannerWindow("character|2024-01-10 06:00:00|0", "character", "Tide", "Furina", "2024-01-10 06:00:00",
                 "2024-01-30 17:59:00", 0, (1,), ())


def pv(pk, pity, outcome, rarity=5, banner=B):
    return PullView(pk, f"I{pk}", 1, "character", rarity, "2024-01-15 10:00:00", pity, outcome,
                    banner.short_name if banner else None, banner.key if banner else None)


def result(pool, total, fives, fours=(), banner_at=None):
    return PoolResult(pool, total, 0, 0, 90, 74, None, list(fives), list(fours), None, None, {},
                      banner_at or {})


def test_pool_stats_excludes_guaranteed_and_unknown_from_win_rate():
    r = result("character", 200, [pv(1, 80, "lost"), pv(2, 10, "guaranteed"), pv(3, 60, "won"),
                                  pv(4, 70, "unknown")], [pv(5, 9, None, 4)])
    s = pool_stats(r)
    assert s == {"pulls": 200, "primogems": 32000, "five": 4, "four": 1, "avg_five_pity": 55.0,
                 "won": 1, "lost": 1, "win_rate": 0.5}
    assert pool_stats(result("standard", 0, []))["avg_five_pity"] is None


def test_overall_stats():
    results = {"character": result("character", 100, [pv(1, 80, "won")]),
               "weapon": result("weapon", 50, [pv(2, 60, "lost")]),
               "standard": result("standard", 10, [pv(3, 10, None)])}
    s = overall_stats(results)
    assert (s["pulls"], s["five"], s["won"], s["lost"], s["win_rate"], s["avg_five_pity"]) == (160, 3, 1, 1, 0.5, 50.0)


def test_monthly_buckets():
    def w(pool, time):
        return Wish(pool=pool, time=time, seq=0, name="x", item_type="weapon", rarity=3, source="game",
                    imported_at=datetime(2024, 1, 1))
    out = monthly([w("character", "2024-02-01 00:00:00"), w("weapon", "2024-01-31 23:59:59"),
                   w("character", "2024-01-05 00:00:00")])
    assert out == [{"month": "2024-01", "character": 1, "weapon": 1, "chronicled": 0, "standard": 0, "beginner": 0},
                   {"month": "2024-02", "character": 1, "weapon": 0, "chronicled": 0, "standard": 0, "beginner": 0}]


def test_pity_histogram():
    h = pity_histogram({"character": result("character", 0, [pv(1, 1, "won"), pv(2, 10, "won"), pv(3, 77, "won"),
                                                             pv(4, 95, "won")])})
    assert len(h) == 9 and h[0] == {"bucket": "1-10", "count": 2}
    assert h[7] == {"bucket": "71-80", "count": 1} and h[8] == {"bucket": "81-90", "count": 1}


def test_banner_timeline():
    r = result("character", 3, [pv(2, 2, "won")], banner_at={1: B, 2: B, 3: None})
    assert banner_timeline({"character": r}) == [
        {"key": B.key, "pool": "character", "name": "Tide", "short_name": "Furina", "start": B.start,
         "pulls": 2, "fives": ["I2"]}]
