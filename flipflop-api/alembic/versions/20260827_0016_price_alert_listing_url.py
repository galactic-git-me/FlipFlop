"""Store the exact marketplace URL that triggers a component price alert."""

from alembic import op
import sqlalchemy as sa

revision = "20260827_0018"
down_revision = "20260827_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("price_alerts", sa.Column("triggered_listing_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("price_alerts", "triggered_listing_url")
