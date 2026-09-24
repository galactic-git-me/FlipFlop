"""Persist Amazon bestseller display prices and sales-velocity text."""
from alembic import op
import sqlalchemy as sa

revision = "20260924_0002"
down_revision = "20260924_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create_all() may have already created these from the ORM model before
    # Alembic runs in a local development database.
    op.execute("ALTER TABLE amazon_bestseller_observations ADD COLUMN IF NOT EXISTS price FLOAT")
    op.execute("ALTER TABLE amazon_bestseller_observations ADD COLUMN IF NOT EXISTS rrp FLOAT")
    op.execute("ALTER TABLE amazon_bestseller_observations ADD COLUMN IF NOT EXISTS sales_velocity VARCHAR(80)")


def downgrade() -> None:
    op.drop_column("amazon_bestseller_observations", "sales_velocity")
    op.drop_column("amazon_bestseller_observations", "rrp")
    op.drop_column("amazon_bestseller_observations", "price")
