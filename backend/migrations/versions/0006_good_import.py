"""phase 6 GOOD import

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_artifact_set",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_table(
        "good_import",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("unmatched", sa.JSON(), nullable=False),
    )
    op.create_table(
        "good_material",
        sa.Column("material_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "good_weapon",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("weapon_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("ascension", sa.Integer(), nullable=False),
        sa.Column("refinement", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("lock", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_good_weapon_weapon_id", "good_weapon", ["weapon_id"])
    op.create_table(
        "good_artifact",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("set_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("main_stat", sa.String(), nullable=False),
        sa.Column("substats", sa.JSON(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("lock", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("good_artifact")
    op.drop_index("ix_good_weapon_weapon_id", table_name="good_weapon")
    op.drop_table("good_weapon")
    op.drop_table("good_material")
    op.drop_table("good_import")
    op.drop_table("game_artifact_set")
