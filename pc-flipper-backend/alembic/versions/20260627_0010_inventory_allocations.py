"""Create inventory_allocations table to link inventory items to flips

Revision ID: 20260627_0010
Revises: 20260627_0009
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = "20260627_0010"
down_revision = "20260627_0009"
depends_on = None


def upgrade():
    op.create_table(
        "inventory_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("flip_id", sa.Integer(), nullable=False),
        sa.Column("quantity_allocated", sa.Integer(), nullable=False),
        sa.Column("cost_per_unit_at_allocation", sa.Float(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory.id"], name="fk_inventory_allocations_inventory_item_id", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["flip_id"], ["flips.id"], name="fk_inventory_allocations_flip_id", ondelete="CASCADE"),
        sa.Index("idx_inventory_allocations_inventory_item_id", "inventory_item_id"),
        sa.Index("idx_inventory_allocations_flip_id", "flip_id"),
    )


def downgrade():
    op.drop_table("inventory_allocations")
