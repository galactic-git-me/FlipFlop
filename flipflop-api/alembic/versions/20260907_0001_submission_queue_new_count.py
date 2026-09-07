"""Persist new-listing counts for durable scan progress.

Revision ID: 20260907_0001
Revises: 20260905_0001
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa


revision = "20260907_0001"
down_revision = "20260905_0001"
depends_on = None


def upgrade():
    op.add_column(
        "submission_queue",
        sa.Column("ingested_new_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("submission_queue", "ingested_new_count")
