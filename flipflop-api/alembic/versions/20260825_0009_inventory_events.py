"""Add append-only physical inventory lifecycle events.

Revision ID: 20260825_0009
Revises: 20260824_0008
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_0009"
down_revision = "20260824_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Development databases may already have this table because the service
    # creates newly registered metadata on startup.  Keep Alembic able to
    # adopt those databases without destroying their audit history.
    if sa.inspect(op.get_bind()).has_table("inventory_events"):
        return
    op.create_table(
        "inventory_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("manual_build_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["manual_build_id"], ["manual_builds.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_inventory_events_inventory_item_id", "inventory_events", ["inventory_item_id"])
    op.create_index("ix_inventory_events_manual_build_id", "inventory_events", ["manual_build_id"])
    op.create_index("ix_inventory_events_event_type", "inventory_events", ["event_type"])
    op.create_index("ix_inventory_events_created_at", "inventory_events", ["created_at"])


def downgrade() -> None:
    op.drop_table("inventory_events")
