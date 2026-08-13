"""Add vendors field to search_configs for per-search vendor configuration.

Revision ID: 20260809_0005
Revises: 20260809_0004
Create Date: 2026-08-09 12:02:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260809_0005"
down_revision = "20260809_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "search_configs",
        sa.Column(
            "vendors",
            sa.JSON(),
            nullable=False,
            server_default='["ebay", "amazon", "vinted", "overclockers", "temu", "cex", "aliexpress"]',
        ),
    )


def downgrade() -> None:
    op.drop_column("search_configs", "vendors")
