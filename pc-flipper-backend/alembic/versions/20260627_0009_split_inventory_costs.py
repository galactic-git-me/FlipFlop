"""Split inventory actual_cost into base_price, shipping_cost, discount_amount

Revision ID: 20260627_0009
Revises: 20260622_0008
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = "20260627_0009"
down_revision = "20260622_0008"
depends_on = None


def upgrade():
    # Add new columns with defaults
    op.add_column("inventory", sa.Column("base_price", sa.Float(), nullable=True))
    op.add_column("inventory", sa.Column("shipping_cost", sa.Float(), server_default="0.0", nullable=False))
    op.add_column("inventory", sa.Column("discount_amount", sa.Float(), server_default="0.0", nullable=False))

    # Migrate data: move existing actual_cost to base_price
    op.execute("UPDATE inventory SET base_price = actual_cost WHERE base_price IS NULL")

    # Make base_price NOT NULL after migration
    op.alter_column("inventory", "base_price", existing_type=sa.Float(), nullable=False)

    # Drop the old actual_cost column
    op.drop_column("inventory", "actual_cost")


def downgrade():
    # Add back the old actual_cost column
    op.add_column("inventory", sa.Column("actual_cost", sa.Float(), nullable=True))

    # Restore data: calculate actual_cost from new columns
    op.execute("UPDATE inventory SET actual_cost = base_price + shipping_cost - discount_amount")

    # Make actual_cost NOT NULL
    op.alter_column("inventory", "actual_cost", existing_type=sa.Float(), nullable=False)

    # Drop new columns
    op.drop_column("inventory", "base_price")
    op.drop_column("inventory", "shipping_cost")
    op.drop_column("inventory", "discount_amount")
