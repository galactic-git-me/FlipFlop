"""Add editable opportunity score component weights."""

from alembic import op
import sqlalchemy as sa

revision = "20260914_0003"
down_revision = "20260914_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, value in (
        ("opportunity_weight_economic_pct", 45.0),
        ("opportunity_weight_desirability_pct", 15.0),
        ("opportunity_weight_market_confidence_pct", 15.0),
        ("opportunity_weight_risk_safety_pct", 5.0),
        ("opportunity_weight_liquidity_pct", 20.0),
    ):
        op.add_column("app_settings", sa.Column(name, sa.Float(), nullable=True))
        op.execute(f"UPDATE app_settings SET {name} = {value} WHERE {name} IS NULL")


def downgrade() -> None:
    for name in (
        "opportunity_weight_liquidity_pct",
        "opportunity_weight_risk_safety_pct",
        "opportunity_weight_market_confidence_pct",
        "opportunity_weight_desirability_pct",
        "opportunity_weight_economic_pct",
    ):
        op.drop_column("app_settings", name)
