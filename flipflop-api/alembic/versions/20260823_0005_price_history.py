"""Add price_history table for Phase 2 F2.1.4

Tracks all price changes with immutable audit trail.
Enables trend analysis and stale pricing detection.

Revision ID: 20260823_0005
Revises: 20260823_0004
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa


revision = "20260823_0005"
down_revision = "20260823_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A pre-Alembic production bootstrap created this table from model
    # metadata. Preserve it and continue the revision chain when present.
    if sa.inspect(op.get_bind()).has_table("price_history"):
        return
    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("manual_build_id", sa.Integer(), nullable=False),
        sa.Column("price_gbp", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("previous_price_gbp", sa.Integer(), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["manual_build_id"], ["manual_builds.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.Index("ix_price_history_manual_build_id", "manual_build_id"),
        sa.Index("ix_price_history_recorded_at", "recorded_at"),
    )


def downgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("price_history"):
        op.drop_table("price_history")
