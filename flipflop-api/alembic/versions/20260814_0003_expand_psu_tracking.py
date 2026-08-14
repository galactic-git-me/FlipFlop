"""Replace has_psu boolean with comprehensive PSU tracking (brand, wattage, rating)

Revision ID: 20260814_0003
Revises: 20260814_0002
Create Date: 2026-08-14 21:35:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260814_0003"
down_revision = "20260814_0002"


def upgrade() -> None:
    # Replace has_psu boolean with comprehensive PSU columns
    op.add_column("listings", sa.Column("psu_included", sa.Boolean(), nullable=False, server_default='false'))
    op.add_column("listings", sa.Column("psu_brand", sa.String(100), nullable=True))
    op.add_column("listings", sa.Column("psu_wattage", sa.Integer(), nullable=True))
    op.add_column("listings", sa.Column("psu_rating", sa.String(20), nullable=True))

    # Data migration: convert old has_psu to psu_included
    op.execute("UPDATE listings SET psu_included = has_psu WHERE has_psu IS NOT NULL")

    # Drop the old column
    op.drop_column("listings", "has_psu")


def downgrade() -> None:
    # Recreate has_psu boolean from psu_included
    op.add_column("listings", sa.Column("has_psu", sa.Boolean(), nullable=False, server_default='true'))
    op.execute("UPDATE listings SET has_psu = psu_included WHERE psu_included IS NOT NULL")

    # Drop new columns
    op.drop_column("listings", "psu_rating")
    op.drop_column("listings", "psu_wattage")
    op.drop_column("listings", "psu_brand")
    op.drop_column("listings", "psu_included")
