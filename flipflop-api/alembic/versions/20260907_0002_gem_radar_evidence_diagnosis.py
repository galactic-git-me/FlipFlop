"""Persist structured Gem Radar evidence diagnosis."""
from alembic import op
import sqlalchemy as sa

revision = "20260907_0002"
down_revision = "20260907_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gem_radar_scored_listings", sa.Column("evidence_status", sa.String(40), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("evidence_reason", sa.String(80), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("evidence_confidence", sa.JSON(), nullable=True))
    op.create_index("ix_gem_radar_scored_listings_evidence_status", "gem_radar_scored_listings", ["evidence_status"])


def downgrade() -> None:
    op.drop_index("ix_gem_radar_scored_listings_evidence_status", table_name="gem_radar_scored_listings")
    op.drop_column("gem_radar_scored_listings", "evidence_confidence")
    op.drop_column("gem_radar_scored_listings", "evidence_reason")
    op.drop_column("gem_radar_scored_listings", "evidence_status")
