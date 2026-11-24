"""Ad Astra sub-project 6: event_log for the Events timeline

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_log",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("start", sa.String(), nullable=True),
        sa.Column("end", sa.String(), nullable=True),
        sa.Column("image", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("calendar_id", sa.Integer(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("event_log")
