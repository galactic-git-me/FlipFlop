"""Persist product review evidence on each marketplace listing observation."""

from alembic import op

revision = "20260924_0001"
down_revision = "20260921_0001"
depends_on = None


def upgrade():
    # DEV databases may have received these additive fields during a live
    # repair before the migration chain was reconciled.
    op.execute("ALTER TABLE gem_radar_listing_observations ADD COLUMN IF NOT EXISTS review_average_rating DOUBLE PRECISION")
    op.execute("ALTER TABLE gem_radar_listing_observations ADD COLUMN IF NOT EXISTS review_count INTEGER")
    op.execute("ALTER TABLE gem_radar_listing_observations ADD COLUMN IF NOT EXISTS review_url VARCHAR(1000)")


def downgrade():
    op.drop_column("gem_radar_listing_observations", "review_url")
    op.drop_column("gem_radar_listing_observations", "review_count")
    op.drop_column("gem_radar_listing_observations", "review_average_rating")
