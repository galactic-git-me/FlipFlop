"""Add canonical identifiers (GTIN, MPN, model_number) to gem_radar_listing_observations.

Enables consolidation of the same product listed under different titles
into a single price bucket (e.g. "9800X3D", "Ryzen 9 9800X3D", "AMD Ryzen 9
9800X3D" all have the same GTIN/MPN/model_number). These are stable,
canonical identifiers across retailers and title variants, unlike title-based
regex matching which fragments them into separate samples.

5-step lookup priority:
1. GTIN (UPC barcode — universal across retailers)
2. MPN (Manufacturer Part Number)
3. Model Number (from vendor API)
4. eBay epid (eBay's own catalog ID)
5. Title-based regex (fallback for older data)

Revision ID: 20260801_0006
Revises: 20260603_0005
Create Date: 2026-08-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260801_0006"
down_revision = "20260603_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add GTIN (Global Trade Item Number / UPC barcode) — canonical product identifier
    op.add_column(
        'gem_radar_listing_observations',
        sa.Column('gtin', sa.String(50), nullable=True, index=True)
    )

    # Add MPN (Manufacturer Part Number) — stable model identifier
    op.add_column(
        'gem_radar_listing_observations',
        sa.Column('mpn', sa.String(100), nullable=True, index=True)
    )

    # Add model_number — from vendor API (e.g. eBay productSummary.modelNumber)
    op.add_column(
        'gem_radar_listing_observations',
        sa.Column('model_number', sa.String(100), nullable=True, index=True)
    )


def downgrade() -> None:
    # Remove columns
    op.drop_column('gem_radar_listing_observations', 'model_number')
    op.drop_column('gem_radar_listing_observations', 'mpn')
    op.drop_column('gem_radar_listing_observations', 'gtin')
