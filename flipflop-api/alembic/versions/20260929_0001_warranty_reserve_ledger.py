"""Add auditable warranty reserve and claim ledgers.

Revision ID: 20260929_0001
Revises: 20260928_0001, vnext_20260928_07
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260929_0001"
down_revision: Union[str, Sequence[str], None] = ("20260928_0001", "vnext_20260928_07")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "warranty_reserves",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("manual_build_id", sa.Integer(), sa.ForeignKey("manual_builds.id"), nullable=True),
        sa.Column("sale_value_gbp", sa.Float(), nullable=False),
        sa.Column("reserve_pct", sa.Float(), nullable=False),
        sa.Column("reserved_amount_gbp", sa.Float(), nullable=False),
        sa.Column("allocated_claim_amount_gbp", sa.Float(), nullable=False, server_default="0"),
        sa.Column("released_amount_gbp", sa.Float(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="held"),
        sa.Column("warranty_started_at", sa.DateTime(), nullable=False),
        sa.Column("warranty_expires_at", sa.DateTime(), nullable=False),
        sa.Column("eligible_at", sa.DateTime(), nullable=True),
        sa.Column("released_at", sa.DateTime(), nullable=True),
        sa.Column("released_by", sa.String(length=320), nullable=True),
        sa.Column("release_note", sa.Text(), nullable=True),
        sa.Column("expiry_alerted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("(order_id IS NOT NULL AND manual_build_id IS NULL) OR (order_id IS NULL AND manual_build_id IS NOT NULL)", name="ck_warranty_reserve_one_sale_source"),
        sa.UniqueConstraint("order_id"),
        sa.UniqueConstraint("manual_build_id"),
    )
    op.create_index("ix_warranty_reserves_order_id", "warranty_reserves", ["order_id"])
    op.create_index("ix_warranty_reserves_manual_build_id", "warranty_reserves", ["manual_build_id"])
    op.create_index("ix_warranty_reserves_status", "warranty_reserves", ["status"])
    op.create_index("ix_warranty_reserves_warranty_expires_at", "warranty_reserves", ["warranty_expires_at"])
    op.create_table(
        "warranty_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reserve_id", sa.Integer(), sa.ForeignKey("warranty_reserves.id"), nullable=False),
        sa.Column("customer_problem_id", sa.Integer(), sa.ForeignKey("customer_problems.id"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="open"),
        sa.Column("issue_summary", sa.Text(), nullable=False),
        sa.Column("approved_cost_gbp", sa.Float(), nullable=False, server_default="0"),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("customer_problem_id"),
    )
    op.create_index("ix_warranty_claims_reserve_id", "warranty_claims", ["reserve_id"])
    op.create_index("ix_warranty_claims_customer_problem_id", "warranty_claims", ["customer_problem_id"])
    op.create_index("ix_warranty_claims_status", "warranty_claims", ["status"])


def downgrade() -> None:
    op.drop_table("warranty_claims")
    op.drop_table("warranty_reserves")
