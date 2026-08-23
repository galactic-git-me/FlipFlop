"""Add CPK versioning fields to manual_builds for soft supersession

Enables "Rebuild with newer CPU" flow without duplicating all component data.
- cpk_version: tag for this build's CPU-Mobo-RAM triplet (same triplet = same version)
- superseded_by_cpk_version: when non-null, newer compatible version exists

Revision ID: 20260823_0003
Revises: 20260823_0002
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa


revision = "20260823_0003"
down_revision = "20260823_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # cpk_version: semantic tag like "Ryzen7-7800X3D_B850_DDR5-48GB"
    # identifies the CPU-Mobo-RAM triplet; same triplet = same version
    op.add_column(
        "manual_builds",
        sa.Column("cpk_version", sa.String(200), nullable=True, index=True),
    )

    # superseded_by_cpk_version: when set, a newer compatible build exists
    # (e.g., newer CPU in same socket/mobo/RAM config)
    # allows storefront to show "Rebuild with X" link without duplicating data
    op.add_column(
        "manual_builds",
        sa.Column("superseded_by_cpk_version", sa.String(200), nullable=True),
    )

    # compatibility_reason: why this version supersedes the previous
    # e.g., "Newer CPU (same socket)", "Lower price", "Better availability"
    op.add_column(
        "manual_builds",
        sa.Column("compatibility_reason", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("manual_builds", "cpk_version")
    op.drop_column("manual_builds", "superseded_by_cpk_version")
    op.drop_column("manual_builds", "compatibility_reason")
