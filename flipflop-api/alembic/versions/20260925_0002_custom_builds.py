"""Add independent custom-build catalogue and sale tracking."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cb_20260925_02_custom"
down_revision: Union[str, None] = "cb_20260925_01_catalogue"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("catalogue_variants", sa.Column("custom_for_builds", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("catalogue_variants", sa.Column("custom_display_price", sa.Float(), nullable=True))
    op.add_column("catalogue_variants", sa.Column("custom_proposed_price", sa.Float(), nullable=True))
    op.add_column("catalogue_variants", sa.Column("custom_cost_snapshot", sa.Float(), nullable=True))
    op.add_column("catalogue_variants", sa.Column("custom_sale_status", sa.String(length=20), nullable=False, server_default="out_of_stock"))
    op.create_index("ix_catalogue_variants_custom_for_builds", "catalogue_variants", ["custom_for_builds"])
    op.create_index("ix_catalogue_variants_custom_sale_status", "catalogue_variants", ["custom_sale_status"])
    op.create_table(
        "custom_build_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("is_live", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("custom_build_settings")
    op.drop_index("ix_catalogue_variants_custom_sale_status", table_name="catalogue_variants")
    op.drop_index("ix_catalogue_variants_custom_for_builds", table_name="catalogue_variants")
    op.drop_column("catalogue_variants", "custom_sale_status")
    op.drop_column("catalogue_variants", "custom_cost_snapshot")
    op.drop_column("catalogue_variants", "custom_proposed_price")
    op.drop_column("catalogue_variants", "custom_display_price")
    op.drop_column("catalogue_variants", "custom_for_builds")
