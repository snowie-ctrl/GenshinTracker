"""phase 5 events, profile, map

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoyolab_snapshot",
        sa.Column("part", sa.String(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "challenge_run",
        sa.Column("kind", sa.String(), primary_key=True),
        sa.Column("season", sa.String(), primary_key=True),
        sa.Column("start", sa.String(), nullable=True),
        sa.Column("end", sa.String(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("teams", sa.JSON(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "event_done",
        sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("done_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("event_done")
    op.drop_table("challenge_run")
    op.drop_table("hoyolab_snapshot")
