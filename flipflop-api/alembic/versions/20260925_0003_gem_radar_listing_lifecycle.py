"""Record active and archived Gem Radar listing availability."""
from alembic import op
import sqlalchemy as sa


revision = "20260925_0003"
down_revision = "20260925_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gem_radar_listing_lifecycle",
        sa.Column("listing_id", sa.String(255), primary_key=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("archive_reason", sa.String(40), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_gem_radar_listing_lifecycle_status", "gem_radar_listing_lifecycle", ["status"])


def downgrade() -> None:
    op.drop_index("ix_gem_radar_listing_lifecycle_status", table_name="gem_radar_listing_lifecycle")
    op.drop_table("gem_radar_listing_lifecycle")
