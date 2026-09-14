"""Add the active/sold target to the unified search-term catalogue."""

from alembic import op
import sqlalchemy as sa


revision = "20260913_0003"
down_revision = "20260913_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "source_search_terms",
        sa.Column("listing_mode", sa.String(length=20), nullable=False, server_default="active"),
    )


def downgrade() -> None:
    op.drop_column("source_search_terms", "listing_mode")
