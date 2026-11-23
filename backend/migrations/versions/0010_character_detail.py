"""Ad Astra sub-project 5: Character detail (per-character targets, talent kit cache)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("character_goal") as b:
        b.add_column(sa.Column("target_constellation", sa.Integer(), nullable=True))
        b.add_column(sa.Column("target_refinement", sa.Integer(), nullable=True))
    op.execute(sa.text("DELETE FROM setting WHERE key = 'default_targets'"))
    op.create_table(
        "game_character_kit",
        sa.Column("character_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("game_character_kit")
    with op.batch_alter_table("character_goal") as b:
        b.drop_column("target_refinement")
        b.drop_column("target_constellation")
