"""Add repair shipment tracking to customer problems.

Revision ID: 20260929_0018
Revises: 20260929_0017
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0018"
down_revision = "20260929_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customer_problems", sa.Column("repair_tracking", sa.JSON(), nullable=True))
    op.add_column("customer_problems", sa.Column("repair_tracking_audit", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("customer_problems", "repair_tracking_audit")
    op.drop_column("customer_problems", "repair_tracking")
