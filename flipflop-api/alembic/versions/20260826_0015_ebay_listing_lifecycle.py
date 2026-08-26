"""Track the authoritative eBay lifecycle of manual-build listings.

Revision ID: 20260826_0015
Revises: 20260825_0014
"""
from alembic import op
import sqlalchemy as sa

revision = "20260826_0015"
down_revision = "20260825_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_builds", sa.Column("ebay_listing_status", sa.String(20), nullable=False, server_default="never_listed"))
    op.add_column("manual_builds", sa.Column("ebay_listing_status_checked_at", sa.DateTime(), nullable=True))
    op.add_column("manual_builds", sa.Column("ebay_listing_end_reason", sa.String(40), nullable=True))
    op.execute("UPDATE manual_builds SET ebay_listing_status = 'unknown' WHERE ebay_listing_id IS NOT NULL")


def downgrade() -> None:
    op.drop_column("manual_builds", "ebay_listing_end_reason")
    op.drop_column("manual_builds", "ebay_listing_status_checked_at")
    op.drop_column("manual_builds", "ebay_listing_status")
