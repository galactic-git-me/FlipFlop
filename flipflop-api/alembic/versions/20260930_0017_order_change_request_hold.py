"""Persist customer order-change requests and sourcing holds.

Revision ID: 20260930_0017
Revises: 20260929_0025
"""
from alembic import op
import sqlalchemy as sa


revision = "20260930_0017"
down_revision = "20260929_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("change_request", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "change_request")
