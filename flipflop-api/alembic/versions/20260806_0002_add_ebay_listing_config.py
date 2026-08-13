"""Add eBay listing configuration fields to manual_builds table.

Revision ID: 0002
Revises: 20260806_0001_add_manual_build_aspects
Create Date: 2026-08-06 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "20260806_0002"
down_revision = "a5f080dc7f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_builds", sa.Column("ebay_condition", sa.String(30), nullable=True))
    op.add_column("manual_builds", sa.Column("ebay_price", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("allow_offers", sa.Boolean(), nullable=False, server_default="1"))
    op.add_column("manual_builds", sa.Column("auto_reject_below_price", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("auction_start_price", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("return_days", sa.Integer(), nullable=False, server_default="30"))
    op.add_column("manual_builds", sa.Column("shipping_method", sa.String(30), nullable=False, server_default="tracked"))
    op.add_column("manual_builds", sa.Column("shipping_cost", sa.Float(), nullable=False, server_default="0.0"))
    op.add_column("manual_builds", sa.Column("handling_time_days", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("manual_builds", sa.Column("ships_to_countries", sa.JSON(), nullable=False, server_default='["GB"]'))
    op.add_column("manual_builds", sa.Column("domestic_only", sa.Boolean(), nullable=False, server_default="1"))


def downgrade() -> None:
    op.drop_column("manual_builds", "domestic_only")
    op.drop_column("manual_builds", "ships_to_countries")
    op.drop_column("manual_builds", "handling_time_days")
    op.drop_column("manual_builds", "shipping_cost")
    op.drop_column("manual_builds", "shipping_method")
    op.drop_column("manual_builds", "return_days")
    op.drop_column("manual_builds", "auction_start_price")
    op.drop_column("manual_builds", "auto_reject_below_price")
    op.drop_column("manual_builds", "allow_offers")
    op.drop_column("manual_builds", "ebay_price")
    op.drop_column("manual_builds", "ebay_condition")
