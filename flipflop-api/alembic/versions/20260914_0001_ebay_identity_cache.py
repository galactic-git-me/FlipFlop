"""Cache the eBay seller identity returned during OAuth status checks."""

from alembic import op
import sqlalchemy as sa


revision = "20260914_0001"
down_revision = "20260913_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("ebay_seller_username", sa.String(length=255), nullable=True))
    op.add_column("app_settings", sa.Column("ebay_seller_email", sa.String(length=320), nullable=True))
    op.add_column("app_settings", sa.Column("ebay_seller_eligible", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("app_settings", "ebay_seller_eligible")
    op.drop_column("app_settings", "ebay_seller_email")
    op.drop_column("app_settings", "ebay_seller_username")
