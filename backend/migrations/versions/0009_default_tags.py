"""Ad Astra sub-project 4: default coloured team tags

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

DEFAULT_TAGS = (("Abyss", "navy"), ("Theater", "purple"), ("Nuke", "red"), ("AoE", "yellow"), ("Boss", "gold"),
                ("Exploration", "green"), ("Main", "teal"), ("Fun", "pink"))


def upgrade() -> None:
    bind = op.get_bind()
    existing = {r[0] for r in bind.execute(sa.text("SELECT name_key FROM tag"))}
    for name, color in DEFAULT_TAGS:
        if name.lower() in existing:
            continue
        bind.execute(sa.text("INSERT INTO tag (name, name_key, color, builtin) VALUES (:n, :k, :c, 0)"),
                     {"n": name, "k": name.lower(), "c": color})


def downgrade() -> None:
    bind = op.get_bind()
    for name, _color in DEFAULT_TAGS:
        bind.execute(sa.text("DELETE FROM tag WHERE name_key = :k AND builtin = 0 "
                             "AND id NOT IN (SELECT tag_id FROM team_tag)"), {"k": name.lower()})
