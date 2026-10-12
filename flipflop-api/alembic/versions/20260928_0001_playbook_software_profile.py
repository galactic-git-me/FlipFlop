"""Add per-cell getting-started software recommendations.

Revision ID: 20260928_0001
Revises: a1b2c3d4e5f6, cb_20260926_04_obs_tags
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260928_0001"
down_revision: Union[str, Sequence[str], None] = (
    "a1b2c3d4e5f6",
    "cb_20260926_04_obs_tags",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("playbooks", sa.Column("software_profile", sa.JSON(), nullable=True))
    op.alter_column(
        "manual_builds",
        "warranty_reserve_pct",
        existing_type=sa.Float(),
        server_default="5",
    )
    op.add_column("manual_builds", sa.Column("shipping_insurance_policy_id", sa.String(length=120), nullable=True))
    op.add_column("manual_builds", sa.Column("shipping_insurance_invoice_id", sa.String(length=120), nullable=True))
    op.add_column("manual_builds", sa.Column("shipping_insurance_cost_gbp", sa.Float(), nullable=True))
    op.add_column("manual_builds", sa.Column("shipping_insurance_status", sa.String(length=40), nullable=False, server_default="not_created"))
    op.add_column("manual_builds", sa.Column("shipping_insurance_created_at", sa.DateTime(), nullable=True))
    op.create_table(
        "getting_started_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manual_build_id", sa.Integer(), sa.ForeignKey("manual_builds.id", ondelete="CASCADE"), nullable=True, unique=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=True, unique=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("playbook_id", sa.Integer(), sa.ForeignKey("playbooks.id"), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False, server_default="ready_to_ship"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="awaiting_review"),
        sa.Column("checklist", sa.JSON(), nullable=False),
        sa.Column("customer_software_selections", sa.JSON(), nullable=False),
        sa.Column("purchased_ai_services", sa.JSON(), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("artifact_index", sa.JSON(), nullable=False),
        sa.Column("private_storage_key", sa.String(length=500), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("manual_build_id IS NOT NULL OR order_id IS NOT NULL", name="ck_getting_started_job_has_build_or_order"),
    )
    op.create_index("ix_getting_started_jobs_customer_id", "getting_started_jobs", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_getting_started_jobs_customer_id", table_name="getting_started_jobs")
    op.drop_table("getting_started_jobs")
    op.drop_column("manual_builds", "shipping_insurance_created_at")
    op.drop_column("manual_builds", "shipping_insurance_status")
    op.drop_column("manual_builds", "shipping_insurance_cost_gbp")
    op.drop_column("manual_builds", "shipping_insurance_invoice_id")
    op.drop_column("manual_builds", "shipping_insurance_policy_id")
    op.alter_column(
        "manual_builds",
        "warranty_reserve_pct",
        existing_type=sa.Float(),
        server_default="3",
    )
    op.drop_column("playbooks", "software_profile")
