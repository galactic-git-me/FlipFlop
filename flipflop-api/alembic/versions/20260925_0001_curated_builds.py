"""Add curated-build curation and playbook segments."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cb_20260925_01_catalogue"
down_revision: Union[str, tuple[str, str], None] = ("e4f7a1c9b3d6", "a5f080dc7f60")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("catalogue_variants", sa.Column("curated_for_builds", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_catalogue_variants_curated_for_builds", "catalogue_variants", ["curated_for_builds"])
    if not sa.inspect(op.get_bind()).has_table("curated_build_segments"):
        op.create_table(
        "curated_build_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_type", sa.String(length=120), nullable=False),
        sa.Column("budget_level", sa.String(length=80), nullable=False),
        sa.Column("budget_min", sa.Float(), nullable=True),
        sa.Column("budget_max", sa.Float(), nullable=True),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.Column("selling_price", sa.Float(), nullable=True),
        sa.Column("proposed_selling_price", sa.Float(), nullable=True),
        sa.Column("component_cost_snapshot", sa.Float(), nullable=True),
        sa.Column("availability_status", sa.String(length=30), nullable=False, server_default="in_stock"),
        sa.Column("is_live", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("regeneration_status", sa.String(length=30), nullable=False, server_default="idle"),
        sa.Column("regeneration_request_id", sa.String(length=100), nullable=True),
        sa.Column("regeneration_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("customer_type", "budget_level", name="uq_curated_segment_type_budget"),
        )


def downgrade() -> None:
    op.drop_table("curated_build_segments")
    op.drop_index("ix_catalogue_variants_curated_for_builds", table_name="catalogue_variants")
    op.drop_column("catalogue_variants", "curated_for_builds")
