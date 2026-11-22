"""Persist separated component price range evidence without changing legacy CPK aggregates."""
from alembic import op
import sqlalchemy as sa


revision = "20261116_0002"
down_revision = "20261116_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "component_price_range_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cpk", sa.String(255), nullable=False),
        sa.Column("condition", sa.String(20), nullable=False),
        sa.Column("market_kind", sa.String(20), nullable=False),
        sa.Column("geography", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="GBP"),
        sa.Column("lower_gbp", sa.Float(), nullable=True),
        sa.Column("median_gbp", sa.Float(), nullable=True),
        sa.Column("upper_gbp", sa.Float(), nullable=True),
        sa.Column("raw_sample_count", sa.Integer(), nullable=False),
        sa.Column("accepted_sample_count", sa.Integer(), nullable=False),
        sa.Column("excluded_outlier_count", sa.Integer(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("references", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("observed_from", sa.DateTime(), nullable=True),
        sa.Column("observed_to", sa.DateTime(), nullable=True),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("cpk", "condition", "market_kind", "geography", "snapshot_date",
                            name="uq_component_price_range_snapshot_key"),
    )
    op.create_index("ix_component_price_range_snapshot_identity", "component_price_range_snapshots",
                    ["cpk", "condition", "market_kind"])


def downgrade() -> None:
    op.drop_index("ix_component_price_range_snapshot_identity", table_name="component_price_range_snapshots")
    op.drop_table("component_price_range_snapshots")
