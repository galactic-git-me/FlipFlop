"""Add model_number canonical identifier to gem_radar_listing_observations.

Captures product model number from vendor API (e.g. eBay productSummary.modelNumber)
for use as 3rd-priority matching key after GTIN/MPN. Example: "100-10000108​4WOF"
for AMD Ryzen 9 9800X3D.

Revision ID: 20260801_0007
Revises: 20260801_0006
Create Date: 2026-08-01 12:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260801_0007"
down_revision = "20260801_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add model_number from vendor API (3rd-priority key after GTIN/MPN)
    op.add_column(
        'gem_radar_listing_observations',
        sa.Column('model_number', sa.String(100), nullable=True, index=True)
    )


def downgrade() -> None:
    op.drop_column('gem_radar_listing_observations', 'model_number')
