"""Add configurable below-market price gates to opportunity tiers."""

from alembic import op
import sqlalchemy as sa


revision = "20260914_0002"
down_revision = "20260914_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("opportunity_super_market_discount_pct", sa.Float(), nullable=True))
    op.add_column("app_settings", sa.Column("opportunity_gem_market_discount_pct", sa.Float(), nullable=True))
    op.execute("UPDATE app_settings SET opportunity_super_market_discount_pct = 35.0 WHERE opportunity_super_market_discount_pct IS NULL")
    op.execute("UPDATE app_settings SET opportunity_gem_market_discount_pct = 25.0 WHERE opportunity_gem_market_discount_pct IS NULL")


def downgrade() -> None:
    op.drop_column("app_settings", "opportunity_gem_market_discount_pct")
    op.drop_column("app_settings", "opportunity_super_market_discount_pct")
