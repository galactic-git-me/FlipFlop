"""Add gem_radar_scan_runs — per search-term scan history

Revision ID: 20260823_0002
Revises: 20260823_0001
Create Date: 2026-08-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20260823_0002"
down_revision = "20260823_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "gem_radar_scan_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("search_term", sa.String(400), nullable=False),
        sa.Column("total_listings_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vendors", sa.JSON(), nullable=False),
        sa.Column("run_by", sa.String(20), nullable=False, server_default="Automatic"),
        sa.Column("duration_seconds", sa.Float(), nullable=False, server_default="0"),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_gem_radar_scan_runs_search_term", "gem_radar_scan_runs", ["search_term"])
    op.create_index("ix_gem_radar_scan_runs_occurred_at", "gem_radar_scan_runs", ["occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_gem_radar_scan_runs_occurred_at", table_name="gem_radar_scan_runs")
    op.drop_index("ix_gem_radar_scan_runs_search_term", table_name="gem_radar_scan_runs")
    op.drop_table("gem_radar_scan_runs")
