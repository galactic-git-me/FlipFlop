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
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("listings")}
    if "has_psu" not in columns and "psu_included" in columns:
        # The current listing model already uses the expanded PSU schema.
        return
    if "has_psu" not in columns:
        raise RuntimeError("Cannot migrate PSU fields: neither has_psu nor psu_included exists")

    # Replace has_psu boolean with comprehensive PSU columns
    if "psu_included" not in columns:
        op.add_column("listings", sa.Column("psu_included", sa.Boolean(), nullable=False, server_default='false'))
    if "psu_brand" not in columns:
        op.add_column("listings", sa.Column("psu_brand", sa.String(100), nullable=True))
    if "psu_wattage" not in columns:
        op.add_column("listings", sa.Column("psu_wattage", sa.Integer(), nullable=True))
    if "psu_rating" not in columns:
        op.add_column("listings", sa.Column("psu_rating", sa.String(20), nullable=True))

    # Data migration: convert old has_psu to psu_included
    op.execute("UPDATE listings SET psu_included = has_psu WHERE has_psu IS NOT NULL")

    # Drop the old column
    if "has_psu" in {item["name"] for item in sa.inspect(op.get_bind()).get_columns("listings")}:
        op.drop_column("listings", "has_psu")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("listings")}
    if "has_psu" in columns:
        return
    if "psu_included" not in columns:
        raise RuntimeError("Cannot restore has_psu: psu_included is missing")
    # Recreate has_psu boolean from psu_included
    op.add_column("listings", sa.Column("has_psu", sa.Boolean(), nullable=False, server_default='true'))
    op.execute("UPDATE listings SET has_psu = psu_included WHERE psu_included IS NOT NULL")
