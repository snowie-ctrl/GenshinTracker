"""phase 3 wishes

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_banner",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("pool", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("short_name", sa.String(), nullable=False),
        sa.Column("start", sa.String(), nullable=False),
        sa.Column("end", sa.String(), nullable=False),
        sa.Column("timezone_dependent", sa.Boolean(), nullable=False),
        sa.Column("timezone_dependent_end", sa.Boolean(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("featured_5", sa.JSON(), nullable=False),
        sa.Column("featured_4", sa.JSON(), nullable=False),
        sa.Column("version", sa.String(), nullable=True),
    )
    op.create_table(
        "wish",
        sa.Column("pk", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id", sa.String(), nullable=True),
        sa.Column("pool", sa.String(), nullable=False),
        sa.Column("gacha_type", sa.String(), nullable=True),
        sa.Column("time", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("id", name="uq_wish_id"),
    )
    op.create_index("ix_wish_pool_time_seq", "wish", ["pool", "time", "seq"])
    op.create_table(
        "wish_import",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=True),
        sa.Column("added", sa.Integer(), nullable=False),
        sa.Column("upgraded", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("backup_file", sa.String(), nullable=True),
        sa.Column("snapshot_file", sa.String(), nullable=True),
    )
    op.create_table(
        "wish_chart",
        sa.Column("pool", sa.String(), primary_key=True),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("set_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("wish_chart")
    op.drop_table("wish_import")
    op.drop_index("ix_wish_pool_time_seq", table_name="wish")
    op.drop_table("wish")
    op.drop_table("game_banner")
