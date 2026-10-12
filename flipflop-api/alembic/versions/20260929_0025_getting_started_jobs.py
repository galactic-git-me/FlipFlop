"""Create the durable Getting Ready workflow table.

Revision ID: 20260929_0025
Revises: 20260929_0024
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0025"
down_revision = "20260929_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The API's legacy startup create_all may already have created this table.
    # Keep this revision safe to apply in either deployment order.
    inspector = sa.inspect(op.get_bind())
    if "getting_started_jobs" in inspector.get_table_names():
        return

    op.create_table(
        "getting_started_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("manual_build_id", sa.Integer(), sa.ForeignKey("manual_builds.id", ondelete="CASCADE"), nullable=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("playbook_id", sa.Integer(), sa.ForeignKey("playbooks.id"), nullable=True),
        sa.Column("source_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
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
        sa.CheckConstraint(
            "manual_build_id IS NOT NULL OR order_id IS NOT NULL",
            name="ck_getting_started_job_has_build_or_order",
        ),
        sa.UniqueConstraint("manual_build_id"),
        sa.UniqueConstraint("order_id"),
    )
    op.create_index("ix_getting_started_jobs_customer_id", "getting_started_jobs", ["customer_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "getting_started_jobs" not in inspector.get_table_names():
        return
    existing_jobs = op.get_bind().execute(
        sa.text("SELECT COUNT(*) FROM getting_started_jobs")
    ).scalar_one()
    if existing_jobs:
        raise RuntimeError(
            "Refusing to drop getting_started_jobs while preparation records exist"
        )
    op.drop_table("getting_started_jobs")
