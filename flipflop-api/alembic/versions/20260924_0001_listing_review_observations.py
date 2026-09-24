"""Persist product review evidence on each marketplace listing observation."""

from alembic import op
import sqlalchemy as sa

revision = "20260924_0001"
down_revision = "20260921_0001"
depends_on = None


def upgrade():
    op.add_column("gem_radar_listing_observations", sa.Column("review_average_rating", sa.Float(), nullable=True))
    op.add_column("gem_radar_listing_observations", sa.Column("review_count", sa.Integer(), nullable=True))
    op.add_column("gem_radar_listing_observations", sa.Column("review_url", sa.String(1000), nullable=True))


def downgrade():
    op.drop_column("gem_radar_listing_observations", "review_url")
    op.drop_column("gem_radar_listing_observations", "review_count")
    op.drop_column("gem_radar_listing_observations", "review_average_rating")
