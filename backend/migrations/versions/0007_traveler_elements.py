"""Ad Astra sub-project 2: Traveler per element, Manekin removed

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-22

Downgrade folds every element back into 10000005 (keeping the current element's goal) and drops
traveler_element. Manekin data deleted by the upgrade is NOT restored.
"""
import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# Frozen copies: later code changes must not change what this migration does.
BASE = 10000005
RAW_TRAVELER = (10000005, 10000007)
MANEKIN = (10000117, 10000118)
ELEMENTS = {"Pyro": 1, "Anemo": 2, "Geo": 3, "Dendro": 4, "Electro": 5, "Hydro": 6, "Cryo": 7}
ELEMENT_IDS = [BASE * 100 + n for n in ELEMENTS.values()]


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")


def _set_setting(bind, key: str, value) -> None:
    bind.execute(sa.text("INSERT INTO setting (key, value) VALUES (:k, :v) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value"),
                 {"k": key, "v": json.dumps(value)})


def _close_slots(bind, team_ids) -> None:
    for tid in team_ids:
        slots = [r[0] for r in bind.execute(sa.text("SELECT slot FROM team_member WHERE team_id=:t ORDER BY slot"),
                                            {"t": tid})]
        if not slots:
            bind.execute(sa.text("DELETE FROM team_tag WHERE team_id=:t"), {"t": tid})
            bind.execute(sa.text("DELETE FROM team WHERE id=:t"), {"t": tid})
            continue
        for new, old in enumerate(slots):
            if new != old:
                bind.execute(sa.text("UPDATE team_member SET slot=:n WHERE team_id=:t AND slot=:o"),
                             {"n": new, "t": tid, "o": old})


def _map_challenge_teams(bind, fn) -> None:
    for kind, season, teams in bind.execute(sa.text("SELECT kind, season, teams FROM challenge_run")).all():
        old = json.loads(teams) if isinstance(teams, str) else teams
        new = [[m for m in (fn(c) for c in team) if m is not None] for team in old or []]
        if new != old:
            bind.execute(sa.text("UPDATE challenge_run SET teams=:v WHERE kind=:k AND season=:s"),
                         {"v": json.dumps(new), "k": kind, "s": season})


def _drop_talent_cache(bind, ids) -> None:
    row = bind.execute(sa.text("SELECT value FROM game_meta WHERE key='talent_ids'")).first()
    if row is None or row[0] is None:
        return
    value = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    kept = {k: v for k, v in value.items() if int(k) not in ids}
    bind.execute(sa.text("UPDATE game_meta SET value=:v WHERE key='talent_ids'"), {"v": json.dumps(kept)})


def upgrade() -> None:
    op.create_table(
        "traveler_element",
        sa.Column("element_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("seen", sa.Boolean(), nullable=False),
        sa.Column("unlocked", sa.Boolean(), nullable=False),
        sa.Column("talent_normal", sa.Integer(), nullable=False),
        sa.Column("talent_skill", sa.Integer(), nullable=False),
        sa.Column("talent_burst", sa.Integer(), nullable=False),
        sa.Column("constellation", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    bind = op.get_bind()
    old = bind.execute(sa.text(
        "SELECT element, icon, talent_normal, talent_skill, talent_burst, constellation "
        "FROM owned_character WHERE character_id=:i"), {"i": BASE}).first()
    element = old.element if old is not None and old.element in ELEMENTS else "Anemo"
    new_id = BASE * 100 + ELEMENTS[element]
    if old is not None:
        bind.execute(sa.text(
            "INSERT INTO traveler_element (element_id, seen, unlocked, talent_normal, talent_skill, talent_burst, "
            "constellation, source, updated_at) VALUES (:e, 1, 0, :n, :s, :b, :c, 'sync', :t)"),
            {"e": new_id, "n": old.talent_normal or 1, "s": old.talent_skill or 1, "b": old.talent_burst or 1,
             "c": old.constellation or 0, "t": _now()})
        _set_setting(bind, "traveler_current_element", element)
        _set_setting(bind, "traveler_body", "boy" if old.icon == "UI_AvatarIcon_PlayerBoy" else "girl")

    for table in ("character_goal", "team_member", "good_weapon", "good_artifact"):
        bind.execute(sa.text(f"UPDATE {table} SET character_id=:n WHERE character_id IN (:a, :b)"),
                     {"n": new_id, "a": RAW_TRAVELER[0], "b": RAW_TRAVELER[1]})

    manekin = {"a": MANEKIN[0], "b": MANEKIN[1]}
    teams = [r[0] for r in bind.execute(sa.text(
        "SELECT DISTINCT team_id FROM team_member WHERE character_id IN (:a, :b)"), manekin)]
    bind.execute(sa.text("DELETE FROM team_member WHERE character_id IN (:a, :b)"), manekin)
    _close_slots(bind, teams)
    for table in ("character_goal", "owned_character", "owned_artifact", "material_gap"):
        bind.execute(sa.text(f"DELETE FROM {table} WHERE character_id IN (:a, :b)"), manekin)
    for table in ("good_weapon", "good_artifact"):
        bind.execute(sa.text(f"UPDATE {table} SET character_id=NULL WHERE character_id IN (:a, :b)"), manekin)
    traveler_raw = {"a": RAW_TRAVELER[0], "b": RAW_TRAVELER[1]}
    for table in ("owned_character", "owned_artifact", "material_gap"):
        bind.execute(sa.text(f"DELETE FROM {table} WHERE character_id IN (:a, :b)"), traveler_raw)
    bind.execute(sa.text("DELETE FROM game_character WHERE id IN (:a, :b, :c, :d)"),
                 {"a": RAW_TRAVELER[0], "b": RAW_TRAVELER[1], "c": MANEKIN[0], "d": MANEKIN[1]})
    bind.execute(sa.text("DELETE FROM game_meta WHERE key='characters_fetched_at'"))  # refresh on next start
    _drop_talent_cache(bind, {*RAW_TRAVELER, *MANEKIN})
    _map_challenge_teams(bind, lambda c: new_id if c in RAW_TRAVELER else (None if c in MANEKIN else c))


def downgrade() -> None:
    bind = op.get_bind()
    row = bind.execute(sa.text("SELECT value FROM setting WHERE key='traveler_current_element'")).first()
    current = json.loads(row[0]) if row is not None and row[0] is not None else None
    keep = BASE * 100 + ELEMENTS[current] if current in ELEMENTS else None
    goal_ids = [r[0] for r in bind.execute(sa.text(
        f"SELECT character_id FROM character_goal WHERE character_id IN ({','.join(map(str, ELEMENT_IDS))}) "
        "ORDER BY character_id"))]
    if goal_ids:
        winner = keep if keep in goal_ids else goal_ids[0]
        bind.execute(sa.text(f"DELETE FROM character_goal WHERE character_id IN "
                             f"({','.join(map(str, ELEMENT_IDS))}) AND character_id != :w"), {"w": winner})
    ids = ",".join(map(str, ELEMENT_IDS))
    # A team may hold two Traveler elements; after folding they would collide on uq_team_member_character.
    bind.execute(sa.text(
        f"DELETE FROM team_member WHERE character_id IN ({ids}) AND slot > ("
        f"SELECT min(m2.slot) FROM team_member m2 WHERE m2.team_id = team_member.team_id "
        f"AND m2.character_id IN ({ids}))"))
    _close_slots(bind, [r[0] for r in bind.execute(sa.text("SELECT id FROM team"))])
    for table in ("character_goal", "team_member", "good_weapon", "good_artifact"):
        bind.execute(sa.text(f"UPDATE {table} SET character_id=:b WHERE character_id IN ({ids})"), {"b": BASE})
    for table in ("owned_character", "owned_artifact", "material_gap"):
        bind.execute(sa.text(f"DELETE FROM {table} WHERE character_id IN ({ids})"))
    bind.execute(sa.text(f"DELETE FROM game_character WHERE id IN ({ids})"))
    bind.execute(sa.text("DELETE FROM setting WHERE key IN ('traveler_current_element', 'traveler_body')"))
    _map_challenge_teams(bind, lambda c: BASE if c in ELEMENT_IDS else c)
    op.drop_table("traveler_element")
