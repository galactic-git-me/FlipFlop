"""Record active and archived Gem Radar listing availability."""
from alembic import op


revision = "20260925_0003"
down_revision = "20260925_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS gem_radar_listing_lifecycle (
            listing_id VARCHAR(255) PRIMARY KEY,
            status VARCHAR(20) NOT NULL,
            archive_reason VARCHAR(40),
            last_seen_at TIMESTAMP NOT NULL,
            archived_at TIMESTAMP,
            updated_at TIMESTAMP NOT NULL
        )
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_gem_radar_listing_lifecycle_status
        ON gem_radar_listing_lifecycle (status)
    """)


def downgrade() -> None:
    op.drop_index("ix_gem_radar_listing_lifecycle_status", table_name="gem_radar_listing_lifecycle")
    op.drop_table("gem_radar_listing_lifecycle")
