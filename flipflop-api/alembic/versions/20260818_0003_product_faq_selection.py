"""Add curated FAQ selections to builds and storefront products.

Revision ID: 20260818_0003
Revises: 20260818_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818_0003"
down_revision = "20260818_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("manual_builds", sa.Column("selected_faq_ids", sa.JSON(), nullable=True))
    op.add_column(
        "products",
        sa.Column("selected_faqs", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("products", "selected_faqs")
    op.drop_column("manual_builds", "selected_faq_ids")
