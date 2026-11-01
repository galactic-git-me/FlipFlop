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
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("inventory")}
    if "actual_cost" not in columns and "base_price" in columns:
        # The canonical current model already stores the split costs. This
        # historical conversion is only needed for databases with the old
        # single actual_cost column.
        return
    if "actual_cost" not in columns:
        raise RuntimeError("Cannot split inventory costs: neither legacy actual_cost nor current base_price exists")

    # Add new columns with defaults
    if "base_price" not in columns:
        op.add_column("inventory", sa.Column("base_price", sa.Float(), nullable=True))
    if "shipping_cost" not in columns:
        op.add_column("inventory", sa.Column("shipping_cost", sa.Float(), server_default="0.0", nullable=False))
    if "discount_amount" not in columns:
        op.add_column("inventory", sa.Column("discount_amount", sa.Float(), server_default="0.0", nullable=False))

    # Migrate data: move existing actual_cost to base_price
    op.execute("UPDATE inventory SET base_price = actual_cost WHERE base_price IS NULL")

    # Make base_price NOT NULL after migration
    op.alter_column("inventory", "base_price", existing_type=sa.Float(), nullable=False)

    # Drop the old actual_cost column
    if "actual_cost" in {item["name"] for item in sa.inspect(op.get_bind()).get_columns("inventory")}:
        op.drop_column("inventory", "actual_cost")


def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns("inventory")}
    if "actual_cost" in columns:
        return
    if "base_price" not in columns:
        raise RuntimeError("Cannot restore inventory actual_cost: base_price is missing")

    # Restore the legacy total additively. Keep split-cost columns so rollback
    # never destroys the current representation or its information.
    op.add_column("inventory", sa.Column("actual_cost", sa.Float(), nullable=True))

    # Restore data: calculate actual_cost from new columns
    op.execute("UPDATE inventory SET actual_cost = base_price + shipping_cost - discount_amount")

    # Make actual_cost NOT NULL
    op.alter_column("inventory", "actual_cost", existing_type=sa.Float(), nullable=False)
