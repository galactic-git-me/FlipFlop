"""Store eBay-native Seller Hub draft identifiers."""

from alembic import op
import sqlalchemy as sa

revision = "20260908_0001"
down_revision = "20260907_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_builds", sa.Column("ebay_draft_id", sa.String(length=100), nullable=True))
    op.add_column("manual_builds", sa.Column("ebay_draft_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("manual_builds", "ebay_draft_url")
    op.drop_column("manual_builds", "ebay_draft_id")
