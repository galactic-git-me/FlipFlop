"""Add needs_attention flag to builds — email monitor sets this for Made-to-Order sales.

Revision ID: 20260723_0022
Revises: 20260723_0021
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20260723_0022"
down_revision = "20260723_0021"
depends_on = None


def upgrade():
    op.add_column("builds", sa.Column("needs_attention", sa.Boolean(), nullable=False, server_default="0"))
    op.create_index("ix_builds_needs_attention", "builds", ["needs_attention"])


def downgrade():
    op.drop_index("ix_builds_needs_attention", table_name="builds")
    op.drop_column("builds", "needs_attention")
