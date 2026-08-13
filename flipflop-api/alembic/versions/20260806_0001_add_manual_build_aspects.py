"""Add generated_aspects (eBay Item Specifics) to manual_builds."""
from alembic import op
import sqlalchemy as sa


revision = "20260806_0001"
down_revision = "a5f080dc7f60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manual_builds",
        sa.Column("generated_aspects", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("manual_builds", "generated_aspects")
