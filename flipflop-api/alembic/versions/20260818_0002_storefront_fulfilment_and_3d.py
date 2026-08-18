"""Add storefront fulfilment, 3D asset and shipment-cover fields.

Revision ID: 20260818_0002
Revises: 20260818_0001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0002"
down_revision = "20260818_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_builds", sa.Column("model_3d_url", sa.String(length=500), nullable=True))
    op.add_column(
        "manual_builds",
        sa.Column("delivery_min_days", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "manual_builds",
        sa.Column("delivery_max_days", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "manual_builds",
        sa.Column("shipping_damage_cover_confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column("products", sa.Column("model_3d_url", sa.String(length=500), nullable=True))
    op.add_column(
        "products",
        sa.Column("fulfilment_type", sa.String(length=30), nullable=False, server_default="prebuilt"),
    )
    op.add_column(
        "products",
        sa.Column("handling_min_days", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "products",
        sa.Column("handling_max_days", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "products",
        sa.Column("delivery_min_days", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "products",
        sa.Column("delivery_max_days", sa.Integer(), nullable=False, server_default="2"),
    )


def downgrade() -> None:
    op.drop_column("products", "delivery_max_days")
    op.drop_column("products", "delivery_min_days")
    op.drop_column("products", "handling_max_days")
    op.drop_column("products", "handling_min_days")
    op.drop_column("products", "fulfilment_type")
    op.drop_column("products", "model_3d_url")
    op.drop_column("manual_builds", "shipping_damage_cover_confirmed")
    op.drop_column("manual_builds", "delivery_max_days")
    op.drop_column("manual_builds", "delivery_min_days")
    op.drop_column("manual_builds", "model_3d_url")
