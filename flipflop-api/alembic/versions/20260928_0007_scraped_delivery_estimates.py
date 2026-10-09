"""Persist parsed listing delivery estimates and their evidence basis."""
from alembic import op
import sqlalchemy as sa

revision = "vnext_20260928_07"
down_revision = "vnext_20260928_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("gem_radar_listing_observations", "gem_radar_scored_listings"):
        op.add_column(table, sa.Column("delivery_working_days", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("delivery_estimate_source", sa.String(length=32), nullable=True))


def downgrade() -> None:
    for table in ("gem_radar_scored_listings", "gem_radar_listing_observations"):
        op.drop_column(table, "delivery_estimate_source")
        op.drop_column(table, "delivery_working_days")
