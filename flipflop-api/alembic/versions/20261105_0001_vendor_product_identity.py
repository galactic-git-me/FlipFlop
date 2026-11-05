"""Store exact merchant product IDs separately from listing IDs."""
from alembic import op
import sqlalchemy as sa


revision = "20261105_0001"
down_revision = "20261104_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "gem_radar_listing_observations",
        sa.Column("vendor_product_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_gem_radar_listing_observations_vendor_product_id",
        "gem_radar_listing_observations",
        ["vendor_product_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_gem_radar_listing_observations_vendor_product_id",
        table_name="gem_radar_listing_observations",
    )
    op.drop_column("gem_radar_listing_observations", "vendor_product_id")
