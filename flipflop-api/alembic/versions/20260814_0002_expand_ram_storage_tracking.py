"""Expand RAM and Storage tracking with brand, model, speed, CAS latency, stick count, and form factor

Revision ID: 20260814_0002
Revises: 20260814_0001
Create Date: 2026-08-14 21:30:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260814_0002"
down_revision = "20260814_0001"


def upgrade() -> None:
    # RAM expansion columns
    op.add_column("listings", sa.Column("ram_brand", sa.String(100), nullable=True))
    op.add_column("listings", sa.Column("ram_model", sa.String(200), nullable=True))
    op.add_column("listings", sa.Column("ram_speed", sa.Integer(), nullable=True))
    op.add_column("listings", sa.Column("ram_cl", sa.Integer(), nullable=True))
    op.add_column("listings", sa.Column("ram_sticks", sa.Integer(), nullable=True))

    # Storage expansion columns
    op.add_column("listings", sa.Column("storage_brand", sa.String(100), nullable=True))
    op.add_column("listings", sa.Column("storage_model", sa.String(200), nullable=True))
    op.add_column("listings", sa.Column("storage_form_factor", sa.String(20), nullable=True))


def downgrade() -> None:
    # RAM columns
    op.drop_column("listings", "ram_sticks")
    op.drop_column("listings", "ram_cl")
    op.drop_column("listings", "ram_speed")
    op.drop_column("listings", "ram_model")
    op.drop_column("listings", "ram_brand")

    # Storage columns
    op.drop_column("listings", "storage_form_factor")
    op.drop_column("listings", "storage_model")
    op.drop_column("listings", "storage_brand")
