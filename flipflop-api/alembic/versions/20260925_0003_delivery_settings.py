"""Add customer storefront delivery promises and speedy surcharge settings."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cb_20260925_03_delivery"
down_revision: Union[str, None] = "20260925_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("speedy_delivery_price_gbp", sa.Float(), nullable=False, server_default="49"))
    op.add_column("app_settings", sa.Column("standard_curated_custom_days", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("app_settings", sa.Column("speedy_curated_custom_days", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("app_settings", sa.Column("standard_prebuilt_days", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("app_settings", sa.Column("speedy_prebuilt_cutoff_hour", sa.Integer(), nullable=False, server_default="14"))


def downgrade() -> None:
    op.drop_column("app_settings", "speedy_prebuilt_cutoff_hour")
    op.drop_column("app_settings", "standard_prebuilt_days")
    op.drop_column("app_settings", "speedy_curated_custom_days")
    op.drop_column("app_settings", "standard_curated_custom_days")
    op.drop_column("app_settings", "speedy_delivery_price_gbp")
