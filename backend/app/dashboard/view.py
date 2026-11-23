"""Dashboard-only shaping: timers, the side-column event list, pity on live banners, build progress."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CharacterGoal, LiveNotes, OwnedCharacter
from app.domain import Current, progress
from app.timeutil import iso

ICONS = {"resin": "UI_ItemIcon_210", "realm": "UI_ItemIcon_204", "transformer": "UI_ItemIcon_220021"}
RESET_KEYS = ("abyss", "theater", "stygian")


def timers(n: LiveNotes) -> list[dict]:
    out = [{"kind": "resin", "label": "Original Resin full", "icon": ICONS["resin"], "ready_at": iso(n.resin_full_at)}]
    if n.realm_currency_full_at is not None:
        out.append({"kind": "realm", "label": "Realm Currency full", "icon": ICONS["realm"],
                    "ready_at": iso(n.realm_currency_full_at)})
    if n.transformer_ready_at is not None:
        out.append({"kind": "transformer", "label": "Parametric Transformer", "icon": ICONS["transformer"],
                    "ready_at": iso(n.transformer_ready_at)})
    for e in n.expeditions or []:
        out.append({"kind": "expedition", "label": "Expedition", "icon": e["icon"], "ready_at": e["return_at"]})
    return sorted(out, key=lambda t: t["ready_at"])


def event_list(events: list[dict], resets: list[dict]) -> list[dict]:
    rows = [{**e, "kind": "event"} for e in events]
    rows += [{"kind": "reset", "id": f"reset-{r['key']}", "key": r["key"], "name": r["label"], "end": r["at"],
              "done": False} for r in resets if r["key"] in RESET_KEYS]
    return sorted(rows, key=lambda r: (r["done"], r.get("end") or "9999"))


def banners_with_pity(banners: list[dict], lines: list[dict]) -> list[dict]:
    by_pool = {line["pool"]: line for line in lines}
    return [{**b, "pity": by_pool.get(b["pool"])} for b in banners]


def build_progress(s: Session) -> dict[int, float | None]:
    from app.targets import stored_targets
    owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
    out: dict[int, float | None] = {}
    for row in s.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")):
        o, t = owned.get(row.character_id), stored_targets(row)
        out[row.character_id] = (progress(Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst), t)
                                 if o is not None and t is not None else None)
    return out
