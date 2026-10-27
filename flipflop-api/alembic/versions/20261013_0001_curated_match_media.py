"""retain all captured media for approved curated product matches

Revision ID: 20261013_0001
Revises: 20261012_merge_heads
Create Date: 2026-10-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261013_0001"
down_revision: Union[str, None] = "20261012_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for table in ("gem_radar_listing_observations", "gem_radar_scored_listings"):
        # A targeted additive repair may already have restored these fields
        # before the full migration chain can be reconciled.
        existing = {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table)}
        for name in ('image_urls', 'video_urls'):
            if name not in existing:
                op.add_column(table, sa.Column(name, sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.execute("UPDATE gem_radar_listing_observations SET image_urls = json_build_array(image_url) WHERE image_url IS NOT NULL AND image_urls::text = '[]'")
    op.execute("UPDATE gem_radar_scored_listings SET image_urls = json_build_array(image_url) WHERE image_url IS NOT NULL AND image_urls::text = '[]'")


def downgrade() -> None:
    for table in ("gem_radar_listing_observations", "gem_radar_scored_listings"):
        op.drop_column(table, "video_urls")
        op.drop_column(table, "image_urls")
