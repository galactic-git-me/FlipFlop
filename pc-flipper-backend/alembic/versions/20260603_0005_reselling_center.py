"""Add eBay listing tracking and image generation fields to flips table.

Revision ID: 20260603_0005
Revises: 20260603_0004
Create Date: 2026-06-03 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260603_0005"
down_revision = "20260603_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add eBay listing tracking columns
    op.add_column('flips', sa.Column('ebay_listing_id', sa.String(50), nullable=True))
    op.add_column('flips', sa.Column('listing_fee_pct', sa.Float(), nullable=True))
    op.add_column('flips', sa.Column('final_value_fee_pct', sa.Float(), nullable=True))
    op.add_column('flips', sa.Column('actual_selling_fee', sa.Float(), nullable=True))

    # Add image generation columns
    op.add_column('flips', sa.Column('generated_images_urls', sa.JSON(), nullable=True))
    op.add_column('flips', sa.Column('image_generation_status', sa.String(50), nullable=True))

    # Create index on ebay_listing_id for efficient lookups
    op.create_index('ix_flips_ebay_listing_id', 'flips', ['ebay_listing_id'], unique=False)


def downgrade() -> None:
    # Drop index
    op.drop_index('ix_flips_ebay_listing_id', table_name='flips')

    # Remove columns
    op.drop_column('flips', 'image_generation_status')
    op.drop_column('flips', 'generated_images_urls')
    op.drop_column('flips', 'actual_selling_fee')
    op.drop_column('flips', 'final_value_fee_pct')
    op.drop_column('flips', 'listing_fee_pct')
    op.drop_column('flips', 'ebay_listing_id')
