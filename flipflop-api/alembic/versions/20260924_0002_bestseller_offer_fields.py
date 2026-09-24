"""Persist Amazon bestseller display prices and sales-velocity text."""
from alembic import op
import sqlalchemy as sa

revision = "20260924_0002"
down_revision = "20260924_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("amazon_bestseller_observations", sa.Column("price", sa.Float(), nullable=True))
    op.add_column("amazon_bestseller_observations", sa.Column("rrp", sa.Float(), nullable=True))
    op.add_column("amazon_bestseller_observations", sa.Column("sales_velocity", sa.String(80), nullable=True))


def downgrade() -> None:
    op.drop_column("amazon_bestseller_observations", "sales_velocity")
    op.drop_column("amazon_bestseller_observations", "rrp")
    op.drop_column("amazon_bestseller_observations", "price")
