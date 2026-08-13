"""Add missing manual_builds columns

Revision ID: 20260807_0001
Revises: 20260806_0003
Create Date: 2026-08-07 22:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "20260807_0001"
down_revision = "20260806_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add missing columns to manual_builds table
    op.add_column("manual_builds", sa.Column("fulfillment_policy_id", sa.String(100), nullable=True))
    op.add_column("manual_builds", sa.Column("package_weight_kg", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("package_length_cm", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("package_width_cm", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("package_height_cm", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("manual_builds", "package_height_cm")
    op.drop_column("manual_builds", "package_width_cm")
    op.drop_column("manual_builds", "package_length_cm")
    op.drop_column("manual_builds", "package_weight_kg")
    op.drop_column("manual_builds", "fulfillment_policy_id")
