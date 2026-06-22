"""Add orders and build capacity tables for storefront checkout

Revision ID: 20260622_0008
Revises: 20260612_0007
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa

revision = "20260622_0008"
down_revision = "20260612_0007"
depends_on = None


def upgrade():
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reference", sa.String(20), nullable=False, unique=True, index=True),
        sa.Column("playbook_id", sa.Integer(), nullable=False),
        sa.Column("playbook_name", sa.String(255), nullable=False),
        sa.Column("build_config", sa.JSON(), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=False),
        sa.Column("delivery_address", sa.JSON(), nullable=False),
        sa.Column("subtotal_gbp", sa.Numeric(10, 2), nullable=False),
        sa.Column("tax_gbp", sa.Numeric(10, 2), nullable=False),
        sa.Column("total_gbp", sa.Numeric(10, 2), nullable=False),
        sa.Column("stripe_session_id", sa.String(255), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending_payment"),
        sa.Column("assigned_build_week", sa.String(10), nullable=True),
        sa.Column("estimated_arrival_date", sa.Date(), nullable=True),
        sa.Column("delivery_at_risk", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("payment_confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["playbook_id"], ["playbooks.id"]),
        sa.Index("idx_orders_status", "status"),
        sa.Index("idx_orders_week", "assigned_build_week"),
        sa.Index("idx_orders_email", "customer_email"),
    )

    op.create_table(
        "build_capacity",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("default_per_week", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "build_capacity_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week", sa.String(10), nullable=False, unique=True, index=True),
        sa.Column("max_builds", sa.Integer(), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Index("idx_capacity_overrides_week", "week"),
    )

    op.execute(
        "INSERT INTO build_capacity (default_per_week, created_at, updated_at) "
        "VALUES (3, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
    )


def downgrade():
    op.drop_table("build_capacity_overrides")
    op.drop_table("build_capacity")
    op.drop_table("orders")
