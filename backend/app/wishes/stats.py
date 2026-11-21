"""Headline numbers and chart series. Pure functions over pity.PoolResult and Wish rows."""
from __future__ import annotations

from collections import Counter, defaultdict

from app.db.models import Wish
from app.wishes.pity import PoolResult, PullView
from app.wishes.types import POOLS

PRIMOGEMS_PER_PULL = 160
BUCKETS = 9


def _summary(pulls: int, fives: list[PullView], four: int, judged: list[PullView]) -> dict:
    won = sum(1 for p in judged if p.outcome == "won")
    lost = sum(1 for p in judged if p.outcome == "lost")
    return {
        "pulls": pulls, "primogems": pulls * PRIMOGEMS_PER_PULL, "five": len(fives), "four": four,
        "avg_five_pity": round(sum(p.pity for p in fives) / len(fives), 1) if fives else None,
        "won": won, "lost": lost, "win_rate": round(won / (won + lost), 3) if won + lost else None,
    }


def pool_stats(r: PoolResult) -> dict:
    return _summary(r.total, r.fives, len(r.fours), r.fives)


def overall_stats(results: dict[str, PoolResult]) -> dict:
    fives = [p for r in results.values() for p in r.fives]
    judged = [p for pool in ("character", "weapon") if pool in results for p in results[pool].fives]
    return _summary(sum(r.total for r in results.values()), fives,
                    sum(len(r.fours) for r in results.values()), judged)


def monthly(rows: list[Wish]) -> list[dict]:
    months: dict[str, Counter] = defaultdict(Counter)
    for w in rows:
        months[w.time[:7]][w.pool] += 1
    return [{"month": m, **{p: months[m].get(p, 0) for p in POOLS}} for m in sorted(months)]


def pity_histogram(results: dict[str, PoolResult]) -> list[dict]:
    counts = [0] * BUCKETS
    for r in results.values():
        for p in r.fives:
            counts[min((p.pity - 1) // 10, BUCKETS - 1)] += 1
    return [{"bucket": f"{i * 10 + 1}-{i * 10 + 10}", "count": c} for i, c in enumerate(counts)]


def banner_timeline(results: dict[str, PoolResult]) -> list[dict]:
    out: dict[str, dict] = {}
    for r in results.values():
        for banner in r.banner_at.values():
            if banner is None:
                continue
            entry = out.setdefault(banner.key, {"key": banner.key, "pool": banner.pool, "name": banner.name,
                                                "short_name": banner.short_name, "start": banner.start,
                                                "pulls": 0, "fives": []})
            entry["pulls"] += 1
        for p in r.fives:
            if p.banner_key in out:
                out[p.banner_key]["fives"].append(p.name)
    return sorted(out.values(), key=lambda e: (e["start"], e["pool"]))
