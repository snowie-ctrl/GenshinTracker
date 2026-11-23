"""Ad Astra sub-project 3: Dashboard (build priority, more HoYoLAB notes fields)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

NOTES_COLUMNS = (
    ("commission_bonus_claimed", sa.Boolean()),
    ("realm_currency_full_at", sa.DateTime()),
    ("transformer_ready_at", sa.DateTime()),
    ("expeditions_max", sa.Integer()),
)


def upgrade() -> None:
    with op.batch_alter_table("character_goal") as b:
        b.add_column(sa.Column("priority", sa.Integer(), nullable=True))
    with op.batch_alter_table("live_notes") as b:
        for name, type_ in NOTES_COLUMNS:
            b.add_column(sa.Column(name, type_, nullable=True))
    bind = op.get_bind()
    ids = [r[0] for r in bind.execute(sa.text(
        "SELECT character_id FROM character_goal WHERE goal = 'build' ORDER BY character_id"))]
    for n, cid in enumerate(ids, start=1):
        bind.execute(sa.text("UPDATE character_goal SET priority = :p WHERE character_id = :c"),
                     {"p": n, "c": cid})


def downgrade() -> None:
    with op.batch_alter_table("live_notes") as b:
        for name, _type in reversed(NOTES_COLUMNS):
            b.drop_column(name)
    with op.batch_alter_table("character_goal") as b:
        b.drop_column("priority")
