"""Store unpublished eBay Inventory API offers for manual-build drafts."""

from alembic import op
import sqlalchemy as sa

revision = "20260907_0021"
down_revision = "20260827_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_builds", sa.Column("ebay_offer_id", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("manual_builds", "ebay_offer_id")
