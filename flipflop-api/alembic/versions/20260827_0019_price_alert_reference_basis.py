"""Record whether an alert reference is a build valuation or market median."""

from alembic import op
import sqlalchemy as sa

revision = "20260827_0019"
down_revision = "20260827_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("price_alerts", sa.Column("reference_basis", sa.String(length=40), nullable=True))
    op.execute("UPDATE price_alerts SET reference_basis = 'build_valuation' WHERE alert_type = 'component'")
    op.execute("UPDATE price_alerts SET reference_basis = 'market_median' WHERE alert_type = 'component' AND triggered_at IS NOT NULL")


def downgrade() -> None:
    op.drop_column("price_alerts", "reference_basis")
