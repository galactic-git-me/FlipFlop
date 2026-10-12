"""Persist the server-priced build alongside checkout addresses.

Revision ID: 20260929_0015
Revises: 20260929_0014
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0015"
down_revision = "20260929_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_checkout_snapshots",
        sa.Column("build_snapshot", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("order_checkout_snapshots", "build_snapshot")
