"""Capture actual selling and after-sale pricing outcomes.

Revision ID: 20260825_0013
Revises: 20260825_0012
"""
from alembic import op
import sqlalchemy as sa

revision = "20260825_0013"
down_revision = "20260825_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("manual_builds")}
    for name in ("marketplace_fees_actual", "promotion_cost_actual", "refund_amount", "warranty_claim_cost"):
        if name not in columns:
            op.add_column("manual_builds", sa.Column(name, sa.Float(), nullable=True))


def downgrade() -> None:
    for name in ("warranty_claim_cost", "refund_amount", "promotion_cost_actual", "marketplace_fees_actual"):
        op.drop_column("manual_builds", name)
