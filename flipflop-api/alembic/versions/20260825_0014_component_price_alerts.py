"""Allow price alerts to monitor preferred components.

Revision ID: 20260825_0014
Revises: 20260825_0013
"""
from alembic import op
import sqlalchemy as sa

revision = "20260825_0014"
down_revision = "20260825_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("price_alerts")}
    if "alert_type" not in columns:
        op.add_column("price_alerts", sa.Column("alert_type", sa.String(20), nullable=False, server_default="build"))
        op.add_column("price_alerts", sa.Column("component_key", sa.String(255), nullable=True))
        op.add_column("price_alerts", sa.Column("component_slot", sa.String(50), nullable=True))
        op.add_column("price_alerts", sa.Column("market_reference_price_gbp", sa.Integer(), nullable=True))
        op.add_column("price_alerts", sa.Column("discount_threshold_pct", sa.Float(), nullable=True))
        op.create_index("ix_price_alerts_alert_type", "price_alerts", ["alert_type"])
        op.create_index("ix_price_alerts_component_key", "price_alerts", ["component_key"])
        op.create_index("ix_price_alerts_component_slot", "price_alerts", ["component_slot"])
        op.execute("CREATE UNIQUE INDEX uq_price_alerts_component_key ON price_alerts (component_key) WHERE alert_type = 'component'")
    op.alter_column("price_alerts", "manual_build_id", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM price_alerts WHERE manual_build_id IS NULL")
    op.alter_column("price_alerts", "manual_build_id", nullable=False)
    op.drop_index("ix_price_alerts_component_slot", table_name="price_alerts")
    op.drop_index("ix_price_alerts_component_key", table_name="price_alerts")
    op.drop_index("ix_price_alerts_alert_type", table_name="price_alerts")
    op.execute("DROP INDEX IF EXISTS uq_price_alerts_component_key")
    for name in ("discount_threshold_pct", "market_reference_price_gbp", "component_slot", "component_key", "alert_type"):
        op.drop_column("price_alerts", name)
