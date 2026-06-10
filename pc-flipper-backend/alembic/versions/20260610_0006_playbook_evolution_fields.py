"""Add playbook evolution fields.

Revision ID: 20260610_0006
Revises: 20260603_0005
Create Date: 2026-06-10 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20260610_0006"
down_revision = "20260603_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("playbooks", sa.Column("target_customer", sa.String(200), nullable=True))
    op.add_column("playbooks", sa.Column("what_they_use_it_for", sa.Text, nullable=True))
    op.add_column("playbooks", sa.Column("what_they_want_from_build", sa.Text, nullable=True))
    op.add_column("playbooks", sa.Column("critical_success_factors", sa.JSON, nullable=True, server_default="[]"))
    op.add_column("playbooks", sa.Column("profit_opportunity_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("market_size_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("resellability_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("liquidity_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("risk_score", sa.Float, nullable=False, server_default="5"))
    op.add_column("playbooks", sa.Column("composite_rank_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("market_growth_direction", sa.String(20), nullable=True))
    op.add_column("playbooks", sa.Column("seasonality", sa.JSON, nullable=True, server_default="{}"))
    op.add_column("playbooks", sa.Column("ideal_build", sa.JSON, nullable=True, server_default="{}"))
    op.add_column("playbooks", sa.Column("pricing_model", sa.JSON, nullable=True, server_default="{}"))
    op.add_column("playbooks", sa.Column("profit_model", sa.JSON, nullable=True, server_default="{}"))
    op.add_column("playbooks", sa.Column("last_reviewed", sa.DateTime, nullable=True))


def downgrade() -> None:
    for col in ["target_customer", "what_they_use_it_for", "what_they_want_from_build",
                "critical_success_factors", "profit_opportunity_score", "market_size_score",
                "resellability_score", "liquidity_score", "risk_score", "composite_rank_score",
                "market_growth_direction", "seasonality", "ideal_build", "pricing_model",
                "profit_model", "last_reviewed"]:
        op.drop_column("playbooks", col)
