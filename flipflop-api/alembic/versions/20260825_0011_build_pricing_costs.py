"""Add persisted fulfilment and warranty pricing inputs.

Revision ID: 20260825_0011
Revises: 20260825_0010
"""
from alembic import op
import sqlalchemy as sa

revision = "20260825_0011"
down_revision = "20260825_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("manual_builds")}
    if "shipping_insurance_cost" not in columns:
        op.add_column("manual_builds", sa.Column("shipping_insurance_cost", sa.Float(), nullable=False, server_default="0"))
    if "packaging_cost" not in columns:
        op.add_column("manual_builds", sa.Column("packaging_cost", sa.Float(), nullable=False, server_default="0"))
    if "warranty_reserve_pct" not in columns:
        op.add_column("manual_builds", sa.Column("warranty_reserve_pct", sa.Float(), nullable=False, server_default="3"))


def downgrade() -> None:
    op.drop_column("manual_builds", "warranty_reserve_pct")
    op.drop_column("manual_builds", "packaging_cost")
    op.drop_column("manual_builds", "shipping_insurance_cost")
