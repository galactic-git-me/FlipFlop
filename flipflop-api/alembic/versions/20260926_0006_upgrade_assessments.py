"""Add customer-owned PC upgrade assessments.

Revision ID: vnext_20260926_06
Revises: vnext_20260926_05
"""
from alembic import op
import sqlalchemy as sa

revision = "vnext_20260926_06"
down_revision = "vnext_20260926_05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "upgrade_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("submitted_spec", sa.JSON(), nullable=False),
        sa.Column("desired_outcome", sa.Text(), nullable=False),
        sa.Column("budget_gbp", sa.Integer(), nullable=False),
        sa.Column("photo_urls", sa.JSON(), nullable=False),
        sa.Column("system_report_url", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("advice", sa.JSON(), nullable=True),
        sa.Column("scope_revision", sa.Integer(), nullable=False),
        sa.Column("approval_required", sa.Boolean(), nullable=False),
        sa.Column("approved_revision", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_upgrade_assessments_customer_id", "upgrade_assessments", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_upgrade_assessments_customer_id", table_name="upgrade_assessments")
    op.drop_table("upgrade_assessments")
