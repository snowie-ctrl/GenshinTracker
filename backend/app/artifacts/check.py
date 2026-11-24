"""Does a character's equipped gear meet its artifact target? Sets and main stats only; substats are
the user's call (they tick Artifacts done)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from app.artifacts.stats import MAIN_SLOTS, SLOT_NAMES, main_key


class GearLike(Protocol):
    slot: int
    set_name: str
    main_stat: str
    icon: str


def check(target: dict | None, equipped: Sequence[GearLike], sets_by_id: dict[int, tuple[str, str | None]]) -> dict:
    t = target or {}
    mains = {slot: list(v) for slot, v in (t.get("main") or {}).items() if v}
    slots = []
    for a in sorted(equipped, key=lambda a: a.slot):
        slot = SLOT_NAMES.get(a.slot, str(a.slot))
        key = main_key(a.main_stat)
        allowed = mains.get(slot) if slot in MAIN_SLOTS else None
        slots.append({"slot": slot, "set_name": a.set_name, "icon": a.icon, "main_stat": a.main_stat,
                      "key": key, "ok": None if not allowed else key in allowed})
    target_sets = t.get("sets") or []
    if not target_sets and not mains:
        return {"status": "none", "sets": [], "slots": slots, "missing": []}
    worn = Counter(a.set_name for a in equipped)
    sets, missing = [], []
    for e in target_sets:
        name, icon = sets_by_id.get(e["set_id"], (f"Set {e['set_id']}", None))
        have = worn.get(name, 0)
        sets.append({"set_id": e["set_id"], "name": name, "icon": icon, "pieces": e["pieces"], "equipped": have})
        if have < e["pieces"]:
            missing.append(f"{e['pieces']}pc {name} ({have}/{e['pieces']})")
    if not equipped:
        missing = ["No artifacts equipped"]
    else:
        for slot in MAIN_SLOTS:
            if slot in mains and not any(s["slot"] == slot and s["ok"] for s in slots):
                missing.append(slot.capitalize())
    return {"status": "missing" if missing else "met", "sets": sets, "slots": slots, "missing": missing}
