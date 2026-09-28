"""Persist scraped Prime eligibility alongside listing delivery evidence."""
from alembic import op
import sqlalchemy as sa

revision = "vnext_20260928_04"
down_revision = "vnext_20260928_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gem_radar_listing_observations", sa.Column("prime_eligible", sa.Boolean(), nullable=True))
    op.add_column("gem_radar_scored_listings", sa.Column("prime_eligible", sa.Boolean(), nullable=True))
    op.add_column("supplier_offer_evidence", sa.Column("prime_eligible", sa.Boolean(), nullable=True))
    op.add_column("supplier_offer_evidence", sa.Column("delivery_estimate_source", sa.String(length=32), nullable=False, server_default="vendor_default"))


def downgrade() -> None:
    op.drop_column("supplier_offer_evidence", "delivery_estimate_source")
    op.drop_column("supplier_offer_evidence", "prime_eligible")
    op.drop_column("gem_radar_scored_listings", "prime_eligible")
    op.drop_column("gem_radar_listing_observations", "prime_eligible")
