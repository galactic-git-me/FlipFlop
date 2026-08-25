"""Add per-unit inventory tracking and reorder rules.

Revision ID: 20260825_0010
Revises: 20260825_0009
Create Date: 2026-08-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260825_0010"
down_revision = "20260825_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("inventory_units"):
        op.create_table(
        "inventory_units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inventory_item_id", sa.Integer(), nullable=False),
        sa.Column("unit_number", sa.Integer(), nullable=False),
        sa.Column("serial_number", sa.String(length=200), nullable=True, unique=True),
        sa.Column("condition_grade", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ordered"),
        sa.Column("storage_location", sa.String(length=200), nullable=True),
        sa.Column("warranty_expires_at", sa.DateTime(), nullable=True),
        sa.Column("test_results", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("photos", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("exception_reason", sa.Text(), nullable=True),
        sa.Column("writeoff_amount", sa.Float(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("inspected_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["inventory_item_id"], ["inventory.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("inventory_item_id", "unit_number", name="uq_inventory_unit_number"),
    )
        op.create_index("ix_inventory_units_inventory_item_id", "inventory_units", ["inventory_item_id"])
        op.create_index("ix_inventory_units_status", "inventory_units", ["status"])
        op.create_index("ix_inventory_units_storage_location", "inventory_units", ["storage_location"])
    if not inspector.has_table("inventory_reorder_rules"):
        op.create_table(
        "inventory_reorder_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("component_type", sa.String(length=50), nullable=False, unique=True),
        sa.Column("minimum_free", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("maximum_free", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("target_free", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
        op.create_index("ix_inventory_reorder_rules_component_type", "inventory_reorder_rules", ["component_type"])


def downgrade() -> None:
    op.drop_table("inventory_reorder_rules")
    op.drop_table("inventory_units")
