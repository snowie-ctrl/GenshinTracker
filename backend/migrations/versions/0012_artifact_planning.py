"""Ad Astra sub-project 8: artifact targets and artifact domains

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("character_goal") as b:
        b.add_column(sa.Column("artifact_target", sa.JSON(), nullable=True))
        b.add_column(sa.Column("artifacts_done", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "game_artifact_domain",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("entrance", sa.String(), nullable=False),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("elements", sa.JSON(), nullable=False),
        sa.Column("set_ids", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("game_artifact_domain")
    with op.batch_alter_table("character_goal") as b:
        b.drop_column("artifacts_done")
        b.drop_column("artifact_target")
