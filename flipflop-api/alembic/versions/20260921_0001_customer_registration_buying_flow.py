"""Add customer registration and buying flow fields.

Revision ID: 20260921_0001
Revises: 20260917_0001
"""
from alembic import op
import sqlalchemy as sa


revision = "20260921_0001"
down_revision = "20260917_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Customer table: Registration data
    op.add_column(
        "customers",
        sa.Column("year_of_birth", sa.Integer(), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("marketing_opt_in", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "customers",
        sa.Column("acquisition_source", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("acquisition_detail", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("profile_metadata", sa.JSON(), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("magic_link_token", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "customers",
        sa.Column("magic_link_expires_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_customers_magic_link_token",
        "customers",
        ["magic_link_token"],
        unique=False,
    )
    
    # Orders table: Buying flow / curated journey data
    op.add_column(
        "orders",
        sa.Column("is_gift", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "orders",
        sa.Column("recipient_age_band", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("discreet_packaging", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "orders",
        sa.Column("urgency", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("is_first_pc", sa.Boolean(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("current_gpu", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("is_business_buyer", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "orders",
        sa.Column("wants_vat_invoice", sa.Boolean(), nullable=False, server_default="0"),
    )
    op.add_column(
        "orders",
        sa.Column("aesthetic_preference", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("journey_budget_min", sa.Float(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("journey_budget_max", sa.Float(), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("journey_customer_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("journey_tier", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    # Orders table
    op.drop_column("orders", "journey_tier")
    op.drop_column("orders", "journey_customer_type")
    op.drop_column("orders", "journey_budget_max")
    op.drop_column("orders", "journey_budget_min")
    op.drop_column("orders", "aesthetic_preference")
    op.drop_column("orders", "wants_vat_invoice")
    op.drop_column("orders", "is_business_buyer")
    op.drop_column("orders", "current_gpu")
    op.drop_column("orders", "is_first_pc")
    op.drop_column("orders", "urgency")
    op.drop_column("orders", "discreet_packaging")
    op.drop_column("orders", "recipient_age_band")
    op.drop_column("orders", "is_gift")
    
    # Customers table
    op.drop_index("ix_customers_magic_link_token", table_name="customers")
    op.drop_column("customers", "magic_link_expires_at")
    op.drop_column("customers", "magic_link_token")
    op.drop_column("customers", "profile_metadata")
    op.drop_column("customers", "acquisition_detail")
    op.drop_column("customers", "acquisition_source")
    op.drop_column("customers", "marketing_opt_in")
    op.drop_column("customers", "year_of_birth")
