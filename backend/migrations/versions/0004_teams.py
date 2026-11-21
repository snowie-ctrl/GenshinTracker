"""phase 4 teams

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "team_member",
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("team.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("slot", sa.Integer(), primary_key=True),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.UniqueConstraint("team_id", "character_id", name="uq_team_member_character"),
    )
    tag = op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("builtin", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("name_key", name="uq_tag_name_key"),
    )
    op.create_table(
        "team_tag",
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("team.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
    )
    op.bulk_insert(tag, [{"id": 1, "name": "Build", "name_key": "build", "color": "orange", "builtin": True}])


def downgrade() -> None:
    op.drop_table("team_tag")
    op.drop_table("tag")
    op.drop_table("team_member")
    op.drop_table("team")
