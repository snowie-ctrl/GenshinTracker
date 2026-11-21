"""The only write path into `wish`: de-duplicate by id, then by (pool, time, name) multisets."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Wish
from app.wishes.types import IncomingWish, ItemResolver

TEMP_SEQ = 1_000_000


@dataclass
class MergeResult:
    added: int = 0
    upgraded: int = 0
    skipped: int = 0
    unknown_names: set[str] = field(default_factory=set)


def merge(session: Session, incoming: list[IncomingWish], source: str, now: datetime) -> MergeResult:
    result = MergeResult()
    if not incoming:
        return result
    resolver = ItemResolver.from_session(session)
    pools = {w.pool for w in incoming}
    existing = list(session.scalars(select(Wish).where(Wish.pool.in_(pools)).order_by(Wish.time, Wish.seq)))
    by_id = {w.id: w for w in existing if w.id}
    by_key: dict[tuple, list[Wish]] = defaultdict(list)
    by_time: dict[tuple, list[Wish]] = defaultdict(list)
    for w in existing:
        by_key[(w.pool, w.time, w.name)].append(w)
        by_time[(w.pool, w.time)].append(w)
    claimed: set[int] = set()
    touched: set[tuple] = set()

    def insert(w: IncomingWish, index: int) -> None:
        item_id = resolver.resolve(w.name)
        row = Wish(id=w.id, pool=w.pool, gacha_type=w.gacha_type, time=w.time, seq=TEMP_SEQ + index,
                   name=w.name, item_id=item_id, item_type=w.item_type, rarity=w.rarity, source=source,
                   imported_at=now)
        session.add(row)
        claimed.add(id(row))
        by_key[(w.pool, w.time, w.name)].append(row)
        by_time[(w.pool, w.time)].append(row)
        if w.id:
            by_id[w.id] = row
        if item_id is None:
            result.unknown_names.add(w.name)
        touched.add((w.pool, w.time))
        result.added += 1

    # 1) rows with real ids: known ids first, so they claim their stored rows
    pending: list[tuple[int, IncomingWish]] = []
    seen: set[str] = set()
    for index, w in enumerate(incoming):
        if not w.id:
            continue
        if w.id in seen:
            result.skipped += 1
            continue
        seen.add(w.id)
        row = by_id.get(w.id)
        if row is not None:
            claimed.add(id(row))
            result.skipped += 1
        else:
            pending.append((index, w))

    # 2) unknown ids: upgrade a matching row, skip a same pull stored under a game id, or insert
    for index, w in pending:
        cands = [r for r in by_key[(w.pool, w.time, w.name)]
                 if id(r) not in claimed and not (source == "game" and r.source == "game")]
        cand = (next((r for r in cands if r.id is None), None)
                or next((r for r in cands if r.source != "game"), None)
                or (cands[0] if cands else None))
        if cand is None:
            insert(w, index)
            continue
        claimed.add(id(cand))
        if cand.id is None or source == "game":
            if cand.id:
                by_id.pop(cand.id, None)
            cand.id, cand.source = w.id, source
            cand.gacha_type = w.gacha_type or cand.gacha_type
            cand.item_id = cand.item_id or resolver.resolve(w.name)
            by_id[w.id] = cand
            touched.add((w.pool, w.time))
            result.upgraded += 1
        else:
            result.skipped += 1

    # 3) id-less rows: insert only the surplus per key, keeping the last occurrences
    idless = [(i, w) for i, w in enumerate(incoming) if not w.id]
    wanted = Counter((w.pool, w.time, w.name) for _, w in idless)
    have = {k: len(by_key[k]) for k in wanted}
    remaining = dict(wanted)
    for index, w in idless:
        k = (w.pool, w.time, w.name)
        surplus = wanted[k] - have[k]
        if remaining[k] <= surplus:
            insert(w, index)
        else:
            result.skipped += 1
        remaining[k] -= 1

    # 4) renumber seq inside every touched timestamp
    session.flush()
    for key in touched:
        group = by_time[key]
        if all(r.id for r in group):
            group.sort(key=lambda r: int(r.id))
        else:
            group.sort(key=lambda r: r.seq)
        for i, r in enumerate(group):
            r.seq = i
    session.flush()
    return result
