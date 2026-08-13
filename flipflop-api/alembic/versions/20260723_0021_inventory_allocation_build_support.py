"""Add build_id support to inventory_allocations — enable allocation to builds not just flips.

Revision ID: 20260723_0021
Revises: 20260723_0020
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20260723_0021"
down_revision = "20260723_0020"
depends_on = None


def upgrade():
    # Add build_id column as nullable
    op.add_column(
        "inventory_allocations",
        sa.Column("build_id", sa.Integer(), sa.ForeignKey("builds.id", ondelete="CASCADE"), nullable=True),
    )
    op.create_index(
        "ix_inventory_allocations_build_id",
        "inventory_allocations",
        ["build_id"],
    )

    # Make flip_id nullable (existing rows stay as-is, only NEW allocations can be build-only)
    op.alter_column("inventory_allocations", "flip_id", existing_type=sa.Integer(), nullable=True)

    # Add check constraint: exactly one of flip_id or build_id must be set
    op.create_check_constraint(
        "ck_exactly_one_target",
        "inventory_allocations",
        "(flip_id IS NOT NULL AND build_id IS NULL) OR (flip_id IS NULL AND build_id IS NOT NULL)",
    )


def downgrade():
    # Remove check constraint
    op.drop_constraint("ck_exactly_one_target", "inventory_allocations", type_="check")

    # Revert flip_id to NOT NULL (will fail if there are build-only allocations — need manual fix)
    op.alter_column("inventory_allocations", "flip_id", existing_type=sa.Integer(), nullable=False)

    # Remove build_id column and its index
    op.drop_index("ix_inventory_allocations_build_id", table_name="inventory_allocations")
    op.drop_column("inventory_allocations", "build_id")
