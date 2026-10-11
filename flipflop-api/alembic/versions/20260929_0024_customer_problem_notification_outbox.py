"""Add durable customer aftercare notification outbox.

Revision ID: 20260929_0024
Revises: 20260929_0023
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0024"
down_revision = "20260929_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_problem_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("problem_id", sa.Integer(), sa.ForeignKey("customer_problems.id"), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("source_key", sa.String(length=160), nullable=False),
        sa.Column("status_code", sa.String(length=40), nullable=False),
        sa.Column("repair_tracking_snapshot", sa.JSON(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_key", name="uq_customer_problem_notifications_source_key"),
    )
    op.create_index(
        "ix_customer_problem_notifications_problem_id",
        "customer_problem_notifications",
        ["problem_id"],
    )
    op.create_index(
        "ix_customer_problem_notifications_order_id",
        "customer_problem_notifications",
        ["order_id"],
    )
    op.create_index(
        "ix_customer_problem_notifications_state",
        "customer_problem_notifications",
        ["state"],
    )


def downgrade() -> None:
    op.drop_index("ix_customer_problem_notifications_state", table_name="customer_problem_notifications")
    op.drop_index("ix_customer_problem_notifications_order_id", table_name="customer_problem_notifications")
    op.drop_index("ix_customer_problem_notifications_problem_id", table_name="customer_problem_notifications")
    op.drop_table("customer_problem_notifications")
