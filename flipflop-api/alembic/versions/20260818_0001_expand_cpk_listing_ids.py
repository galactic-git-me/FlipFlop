"""Expand CPK listing IDs for vendor-qualified product slugs.

Revision ID: 20260818_0001
Revises: 20260817_0001
"""
from alembic import op
import sqlalchemy as sa


revision = "20260818_0001"
down_revision = "20260817_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "gem_radar_listing_cpk",
        "listing_id",
        existing_type=sa.String(length=50),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    op.alter_column(
        "gem_radar_cpk_listing_price",
        "listing_id",
        existing_type=sa.String(length=50),
        type_=sa.String(length=255),
        existing_nullable=False,
    )


def downgrade():
    # Refuse to silently truncate identifiers on downgrade. PostgreSQL will
    # raise if any stored value exceeds the old limit.
    op.alter_column(
        "gem_radar_cpk_listing_price",
        "listing_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
    op.alter_column(
        "gem_radar_listing_cpk",
        "listing_id",
        existing_type=sa.String(length=255),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
