"""Ad Astra sub-project 9: HoYoLAB artifact-stat recommendations

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stat_recommendation",
        sa.Column("character_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stat_recommendation")
