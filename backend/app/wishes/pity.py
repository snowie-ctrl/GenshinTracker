"""Pity, 5★ outcomes, next-5★ state, fate points and the Capturing Radiance estimate.
Pure functions over Wish rows (ordered by time, seq within a pool) and GameBanner rows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameBanner, GameCharacter, GameWeapon, Wish, WishChart
from app.wishes.types import PITY, POOLS, server_local_now, shift_time

RADIANCE_START = "2024-08-28 00:00:00"
# Consecutive lost 50/50s at which the next 50/50 is "likely Radiance" (community estimate).
# Set from docs/superpowers/notes/2026-11-20-phase3-wish-findings.md; None = show the count only.
RADIANCE_LIKELY_AT: int | None = None
ASIA_OFFSET = 8


@dataclass(frozen=True)
class BannerWindow:
    key: str
    pool: str
    name: str
    short_name: str
    start: str
    end: str
    order: int
    featured_5: tuple[int, ...]
    featured_4: tuple[int, ...]
    version: str | None = None


@dataclass
class PullView:
    pk: int
    name: str
    item_id: int | None
    item_type: str
    rarity: int
    time: str
    pity: int
    outcome: str | None
    banner: str | None
    banner_key: str | None


@dataclass
class PoolResult:
    pool: str
    total: int
    pity5: int
    pity4: int
    hard: int
    soft: int | None
    next_state: str | None
    fives: list[PullView]
    fours: list[PullView]
    fate: dict | None
    radiance: dict | None
    pity_at: dict[int, int] = field(default_factory=dict)
    banner_at: dict[int, "BannerWindow | None"] = field(default_factory=dict)

    @property
    def in_soft(self) -> bool:
        return self.soft is not None and self.pity5 + 1 >= self.soft


def banner_windows(banners: Iterable[GameBanner], offset: int) -> dict[str, list[BannerWindow]]:
    out: dict[str, list[BannerWindow]] = {p: [] for p in POOLS}
    for b in banners:
        start = shift_time(b.start, ASIA_OFFSET, offset) if b.timezone_dependent else b.start
        end = shift_time(b.end, ASIA_OFFSET, offset) if b.timezone_dependent_end else b.end
        out.setdefault(b.pool, []).append(BannerWindow(b.key, b.pool, b.name, b.short_name, start, end, b.order,
                                                       tuple(b.featured_5), tuple(b.featured_4), b.version))
    for windows in out.values():
        windows.sort(key=lambda w: (w.start, w.order))
    return out


def attribute(w: Wish, windows: list[BannerWindow]) -> BannerWindow | None:
    hits = [b for b in windows if b.start <= w.time <= b.end]
    if not hits:
        return None
    if w.pool != "character" or len(hits) == 1:
        return hits[0]
    if w.gacha_type in ("301", "400"):
        want = 1 if w.gacha_type == "400" else 0
        return next((b for b in hits if b.order == want), None)     # no such banner: unattributed
    featured = next((b for b in hits if w.item_id is not None and w.item_id in b.featured_5), None)
    if featured is not None:
        return featured
    return next((b for b in hits if b.order == 0), hits[0])


def _outcome(w: Wish, banner: BannerWindow | None, prev_lost: bool | None) -> tuple[str, bool | None]:
    if banner is None or not banner.featured_5 or w.item_id is None:
        return "unknown", None
    if w.item_id in banner.featured_5:
        if prev_lost is None:
            return "unknown", False
        return ("guaranteed" if prev_lost else "won"), False
    return "lost", True


def _radiance(count: int | None, outcome: str) -> int | None:
    if outcome == "won":
        return 0
    if outcome == "lost":
        return None if count is None else count + 1
    if outcome == "unknown":
        return None
    return count                                   # guaranteed: unchanged


def _view(w: Wish, pity: int, outcome: str | None, banner: BannerWindow | None) -> PullView:
    return PullView(w.pk, w.name, w.item_id, w.item_type, w.rarity, w.time, pity, outcome,
                    banner.short_name if banner else None, banner.key if banner else None)


def _fate(pool: str, chart: WishChart | None, current: BannerWindow | None, fives: list[PullView],
          offset: int, names: dict[int, str]) -> dict:
    choices = [{"item_id": i, "name": names.get(i, str(i))} for i in (current.featured_5 if current else ())]
    base = {"points": None, "max": 1, "chart_item_id": None, "chart_name": None, "choices": choices,
            "banner": current.short_name if current else None}
    if chart is None or current is None or chart.item_id not in current.featured_5:
        return base
    set_local = server_local_now(chart.set_at, offset)
    if not (current.start <= set_local <= current.end):
        return base
    points = 0
    for p in fives:
        if p.time < set_local:
            continue
        hit = p.item_id == chart.item_id
        if pool == "chronicled":
            p.outcome = "charted" if hit else "not_charted"
        if hit:
            return base                            # charted item obtained: the chart is used up
        points = 1
    return {**base, "points": points, "chart_item_id": chart.item_id, "chart_name": names.get(chart.item_id)}


def summarize_pool(pool: str, rows: list[Wish], windows: list[BannerWindow], chart: WishChart | None,
                   now_local: str, offset: int, names: dict[int, str]) -> PoolResult:
    rule = PITY[pool]
    c5 = c4 = 0
    prev_lost: bool | None = False
    radiance: int | None = 0
    fives: list[PullView] = []
    fours: list[PullView] = []
    pity_at: dict[int, int] = {}
    banner_at: dict[int, BannerWindow | None] = {}
    for w in rows:
        c5 += 1
        c4 += 1
        banner = attribute(w, windows)
        banner_at[w.pk], pity_at[w.pk] = banner, c5
        if w.rarity == 5:
            outcome = None
            if pool in ("character", "weapon"):
                outcome, prev_lost = _outcome(w, banner, prev_lost)
                if pool == "character" and w.time >= RADIANCE_START:
                    radiance = _radiance(radiance, outcome)
            fives.append(_view(w, c5, outcome, banner))
            c5 = c4 = 0
        elif w.rarity == 4:
            fours.append(_view(w, c4, None, banner))
            c4 = 0
    current = next((b for b in reversed(windows) if b.start <= now_local <= b.end), None)
    fate = _fate(pool, chart, current, fives, offset, names) if pool in ("weapon", "chronicled") else None
    next_state = None
    if pool in ("character", "weapon"):
        next_state = ("unknown" if prev_lost is None else "guaranteed" if prev_lost
                      else "50/50" if pool == "character" else "75/25")
    rad = None
    if pool == "character":
        likely = (radiance >= RADIANCE_LIKELY_AT
                  if radiance is not None and RADIANCE_LIKELY_AT is not None else None)
        rad = {"losses": radiance, "likely": likely, "estimate": True}
    return PoolResult(pool, len(rows), c5, c4, rule.hard, rule.soft, next_state, fives, fours, fate, rad,
                      pity_at, banner_at)


def load_names(session: Session) -> dict[int, str]:
    names = {i: n for i, n in session.execute(select(GameWeapon.id, GameWeapon.name))}
    names.update({i: n for i, n in session.execute(select(GameCharacter.id, GameCharacter.name))})
    return names


def summarize(session: Session, now_utc: datetime, offset: int) -> dict[str, PoolResult]:
    rows = list(session.scalars(select(Wish).order_by(Wish.time, Wish.seq, Wish.pk)))
    windows = banner_windows(list(session.scalars(select(GameBanner))), offset)
    charts = {c.pool: c for c in session.scalars(select(WishChart))}
    names = load_names(session)
    now_local = server_local_now(now_utc, offset)
    by_pool: dict[str, list[Wish]] = {p: [] for p in POOLS}
    for w in rows:
        by_pool.setdefault(w.pool, []).append(w)
    return {p: summarize_pool(p, by_pool[p], windows.get(p, []), charts.get(p), now_local, offset, names)
            for p in POOLS}
