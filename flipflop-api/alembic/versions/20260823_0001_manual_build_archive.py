"""Add is_archived to manual_builds so deletion never destroys the row

Revision ID: 20260823_0001
Revises: 20260820_0001
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20260823_0001"
down_revision = "20260820_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manual_builds",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("manual_builds", "is_archived")
