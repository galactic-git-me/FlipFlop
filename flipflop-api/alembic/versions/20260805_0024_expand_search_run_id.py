"""Expand search_run_id column to varchar(255)."""
from alembic import op
import sqlalchemy as sa


revision = "20260805_0024"
down_revision = "20260801_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "gem_radar_scored_listings",
        "search_run_id",
        existing_type=sa.String(30),
        type_=sa.String(255),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "gem_radar_scored_listings",
        "search_run_id",
        existing_type=sa.String(255),
        type_=sa.String(30),
        existing_nullable=True,
    )
