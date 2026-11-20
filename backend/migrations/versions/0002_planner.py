"""phase 2 planner

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_material",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("yatta_type", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("family", sa.Integer(), nullable=True),
        sa.Column("craft_from", sa.Integer(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("detail_fetched", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "game_domain",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("city", sa.Integer(), nullable=True),
        sa.Column("weekdays", sa.JSON(), nullable=False),
        sa.Column("material_ids", sa.JSON(), nullable=False),
    )
    op.create_table(
        "game_weapon",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("weapon_type", sa.String(), nullable=False),
    )
    op.create_table(
        "material_gap",
        sa.Column("character_id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), primary_key=True),
        sa.Column("need", sa.Integer(), nullable=False),
        sa.Column("short", sa.Integer(), nullable=False),
    )
    op.create_table(
        "material_total",
        sa.Column("material_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("need", sa.Integer(), nullable=False),
        sa.Column("short", sa.Integer(), nullable=False),
        sa.Column("spare", sa.Integer(), nullable=False),
    )
    op.create_table(
        "gap_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("skipped", sa.JSON(), nullable=False),
    )
    op.create_table(
        "weekly_boss_done",
        sa.Column("boss", sa.String(), primary_key=True),
        sa.Column("week_start", sa.DateTime(), primary_key=True),
    )
    op.add_column("owned_character", sa.Column("weapon_id", sa.Integer(), nullable=True))
    op.add_column("live_notes", sa.Column("weekly_discounts_left", sa.Integer(), nullable=True))
    op.add_column("live_notes", sa.Column("weekly_discounts_max", sa.Integer(), nullable=True))
    op.add_column("character_goal", sa.Column("planned_weapon_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("character_goal") as b:
        b.drop_column("planned_weapon_id")
    with op.batch_alter_table("live_notes") as b:
        b.drop_column("weekly_discounts_max")
        b.drop_column("weekly_discounts_left")
    with op.batch_alter_table("owned_character") as b:
        b.drop_column("weapon_id")
    for table in ("weekly_boss_done", "gap_run", "material_total", "material_gap",
                  "game_weapon", "game_domain", "game_material"):
        op.drop_table(table)
