"""Add deferred_publish_at to manual_builds table

Revision ID: 20260814_0001
Revises: 20260813_0018
Create Date: 2026-08-14 21:22:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "20260814_0001"
down_revision = "20260813_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_builds", sa.Column("deferred_publish_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("manual_builds", "deferred_publish_at")
