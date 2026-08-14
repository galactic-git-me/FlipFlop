"""Add comprehensive PC case tracking to listings

Revision ID: 20260814_0004
Revises: 20260814_0003
Create Date: 2026-08-14 21:40:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = "20260814_0004"
down_revision = "20260814_0003"


def upgrade() -> None:
    # Add case tracking columns to listings
    op.add_column("listings", sa.Column("case_brand", sa.String(100), nullable=True))
    op.add_column("listings", sa.Column("case_model", sa.String(200), nullable=True))
    op.add_column("listings", sa.Column("case_form_factor", sa.String(20), nullable=True))
    op.add_column("listings", sa.Column("case_color", sa.String(50), nullable=True))
    op.add_column("listings", sa.Column("case_catalogue_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    # Drop case columns
    op.drop_column("listings", "case_catalogue_id")
    op.drop_column("listings", "case_color")
    op.drop_column("listings", "case_form_factor")
    op.drop_column("listings", "case_model")
    op.drop_column("listings", "case_brand")
