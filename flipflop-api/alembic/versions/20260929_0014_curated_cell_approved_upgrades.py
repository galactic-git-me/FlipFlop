"""Persist the reviewed two-upgrade offer on each curated cell.

Revision ID: 20260929_0014
Revises: 20260929_0013
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0014"
down_revision = "20260929_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "curated_build_segments",
        sa.Column("approved_upgrades", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.alter_column("curated_build_segments", "approved_upgrades", server_default=None)


def downgrade() -> None:
    op.drop_column("curated_build_segments", "approved_upgrades")
