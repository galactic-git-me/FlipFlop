"""Add customer-scoped aftercare problem cases."""

from alembic import op
import sqlalchemy as sa

revision = "20260819_0001"
down_revision = "20260818_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_problems",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="received"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_customer_problems_order_id", "customer_problems", ["order_id"])
    op.create_index("ix_customer_problems_customer_id", "customer_problems", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_customer_problems_customer_id", table_name="customer_problems")
    op.drop_index("ix_customer_problems_order_id", table_name="customer_problems")
    op.drop_table("customer_problems")
