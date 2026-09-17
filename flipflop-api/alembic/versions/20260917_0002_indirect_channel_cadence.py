"""Add the shared cadence for indirect cross-listing channels."""
from alembic import op
import sqlalchemy as sa


revision = "20260917_0002"
down_revision = "20260917_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("indirect_channel_recreate_interval_days", sa.Integer(), nullable=False, server_default="7"),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "indirect_channel_recreate_interval_days")
