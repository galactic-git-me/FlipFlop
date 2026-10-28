"""Align scored-listing ORM market fields with the database schema."""
from alembic import op


revision = "20260925_0001"
down_revision = "20260924_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # These fields were previously added by a standalone setup script, so
    # tolerate databases where some or all columns already exist.
    op.execute("ALTER TABLE gem_radar_scored_listings ADD COLUMN IF NOT EXISTS market_lower_price FLOAT")
    op.execute("ALTER TABLE gem_radar_scored_listings ADD COLUMN IF NOT EXISTS market_median_price FLOAT")
    op.execute("ALTER TABLE gem_radar_scored_listings ADD COLUMN IF NOT EXISTS market_upper_price FLOAT")
    op.execute("ALTER TABLE gem_radar_scored_listings ADD COLUMN IF NOT EXISTS pct_offset FLOAT")
    op.execute("ALTER TABLE gem_radar_scored_listings ADD COLUMN IF NOT EXISTS recommendation VARCHAR(255)")


def downgrade() -> None:
    op.execute("ALTER TABLE gem_radar_scored_listings DROP COLUMN IF EXISTS recommendation")
    op.execute("ALTER TABLE gem_radar_scored_listings DROP COLUMN IF EXISTS pct_offset")
    op.execute("ALTER TABLE gem_radar_scored_listings DROP COLUMN IF EXISTS market_upper_price")
    op.execute("ALTER TABLE gem_radar_scored_listings DROP COLUMN IF EXISTS market_median_price")
    op.execute("ALTER TABLE gem_radar_scored_listings DROP COLUMN IF EXISTS market_lower_price")
