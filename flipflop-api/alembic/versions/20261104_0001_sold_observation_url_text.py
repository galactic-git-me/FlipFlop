"""Preserve long marketplace evidence URLs in sold observations.

Revision ID: 20261104_0001
Revises: 20261103_0002
Create Date: 2026-11-04
"""
from alembic import op
import sqlalchemy as sa


revision = "20261104_0001"
down_revision = "20261103_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "gem_radar_sold_observations", "source_url",
        existing_type=sa.String(length=1000), type_=sa.Text(), existing_nullable=True,
    )


def downgrade() -> None:
    # PostgreSQL rejects this narrowing if long URLs exist. Do not use an
    # explicit cast/substring: rollback must never silently truncate evidence.
    op.alter_column(
        "gem_radar_sold_observations", "source_url",
        existing_type=sa.Text(), type_=sa.String(length=1000), existing_nullable=True,
    )
