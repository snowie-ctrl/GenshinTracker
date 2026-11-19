"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_character",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("element", sa.String(), nullable=True),
        sa.Column("weapon_type", sa.String(), nullable=False),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("splash", sa.String(), nullable=False),
        sa.Column("release_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "game_meta",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
    )
    op.create_table(
        "owned_character",
        sa.Column("character_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("element", sa.String(), nullable=True),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("constellation", sa.Integer(), nullable=False),
        sa.Column("friendship", sa.Integer(), nullable=False),
        sa.Column("talent_normal", sa.Integer(), nullable=True),
        sa.Column("talent_skill", sa.Integer(), nullable=True),
        sa.Column("talent_burst", sa.Integer(), nullable=True),
        sa.Column("weapon_name", sa.String(), nullable=False),
        sa.Column("weapon_icon", sa.String(), nullable=False),
        sa.Column("weapon_rarity", sa.Integer(), nullable=False),
        sa.Column("weapon_level", sa.Integer(), nullable=False),
        sa.Column("weapon_refinement", sa.Integer(), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "owned_artifact",
        sa.Column("character_id", sa.Integer(), primary_key=True),
        sa.Column("slot", sa.Integer(), primary_key=True),
        sa.Column("set_name", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("main_stat", sa.String(), nullable=False),
        sa.Column("substats", sa.JSON(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
    )
    op.create_table(
        "live_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resin", sa.Integer(), nullable=False),
        sa.Column("resin_max", sa.Integer(), nullable=False),
        sa.Column("resin_full_at", sa.DateTime(), nullable=False),
        sa.Column("commissions_done", sa.Integer(), nullable=False),
        sa.Column("commissions_max", sa.Integer(), nullable=False),
        sa.Column("realm_currency", sa.Integer(), nullable=False),
        sa.Column("realm_currency_max", sa.Integer(), nullable=False),
        sa.Column("expeditions", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "sync_run",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("parts", sa.JSON(), nullable=False),
    )
    op.create_table(
        "character_goal",
        sa.Column("character_id", sa.Integer(), primary_key=True),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("target_level", sa.Integer(), nullable=True),
        sa.Column("target_normal", sa.Integer(), nullable=True),
        sa.Column("target_skill", sa.Integer(), nullable=True),
        sa.Column("target_burst", sa.Integer(), nullable=True),
        sa.Column("target_weapon_level", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "setting",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    for table in (
        "setting", "character_goal", "sync_run", "live_notes",
        "owned_artifact", "owned_character", "game_meta", "game_character",
    ):
        op.drop_table(table)
