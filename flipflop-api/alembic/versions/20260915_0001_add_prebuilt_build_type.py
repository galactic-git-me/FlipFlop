"""Add the PREBUILT value required by the storefront listing workflow.

Revision ID: 20260915_0001
Revises: 20260914_0003
Create Date: 2026-09-15
"""
from alembic import op


revision = "20260915_0001"
down_revision = "20260914_0003"
depends_on = None


def upgrade():
    # SQLAlchemy persists the enum member name (PREBUILT), not its lowercase
    # Python value, because the existing model uses Enum(BuildType).
    op.execute("ALTER TYPE buildtype ADD VALUE IF NOT EXISTS 'PREBUILT'")


def downgrade():
    # PostgreSQL cannot remove an enum value safely in place. Leaving the
    # value during downgrade is preferable to risking existing rows.
    pass
