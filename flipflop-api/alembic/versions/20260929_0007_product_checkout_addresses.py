"""Persist delivery and billing snapshots for direct storefront checkouts.

Revision ID: 20260929_0007
Revises: 20260929_0006
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0007"
down_revision = "20260929_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("checkout_addresses", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "checkout_addresses")
