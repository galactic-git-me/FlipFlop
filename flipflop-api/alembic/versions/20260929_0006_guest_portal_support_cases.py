"""Allow scoped guest portals to submit support and warranty cases.

Revision ID: 20260929_0006
Revises: 20260929_0005
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0006"
down_revision = "20260929_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("customer_problems", "order_id", existing_type=sa.Integer(), nullable=True)
    op.alter_column("customer_problems", "customer_id", existing_type=sa.Integer(), nullable=True)
    op.add_column(
        "customer_problems",
        sa.Column("manual_build_id", sa.Integer(), sa.ForeignKey("manual_builds.id"), nullable=True),
    )
    op.add_column(
        "customer_problems",
        sa.Column("portal_grant_id", sa.Integer(), sa.ForeignKey("portal_access_grants.id"), nullable=True),
    )
    op.create_index("ix_customer_problems_manual_build_id", "customer_problems", ["manual_build_id"])
    op.create_index("ix_customer_problems_portal_grant_id", "customer_problems", ["portal_grant_id"])
    existing_checks = {check["name"] for check in sa.inspect(op.get_bind()).get_check_constraints("customer_problems")}
    if "ck_customer_problem_one_source" not in existing_checks:
        op.create_check_constraint(
            "ck_customer_problem_one_source",
            "customer_problems",
            "(order_id IS NOT NULL AND manual_build_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    has_guest_cases = bind.execute(
        sa.text("SELECT 1 FROM customer_problems WHERE manual_build_id IS NOT NULL OR portal_grant_id IS NOT NULL LIMIT 1")
    ).first()
    if has_guest_cases:
        raise RuntimeError("Cannot downgrade while guest build support cases exist")
    op.drop_constraint("ck_customer_problem_one_source", "customer_problems", type_="check")
    op.drop_index("ix_customer_problems_portal_grant_id", table_name="customer_problems")
    op.drop_index("ix_customer_problems_manual_build_id", table_name="customer_problems")
    op.drop_column("customer_problems", "portal_grant_id")
    op.drop_column("customer_problems", "manual_build_id")
    op.alter_column("customer_problems", "customer_id", existing_type=sa.Integer(), nullable=False)
    op.alter_column("customer_problems", "order_id", existing_type=sa.Integer(), nullable=False)
