"""Add demand scores to search terms and listings

Revision ID: 20260603_0004
Revises: 20260518_0003
Create Date: 2026-06-03
"""
from alembic import op
import sqlalchemy as sa

revision = "20260603_0004"
down_revision = "20260518_0003"
depends_on = None


def upgrade():
    # source_search_terms: demand intelligence columns
    with op.batch_alter_table("source_search_terms") as batch:
        batch.add_column(sa.Column("demand_score", sa.Float(), nullable=False, server_default="5.0"))
        batch.add_column(sa.Column("is_baseline", sa.Boolean(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("zero_results_streak", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("last_result_at", sa.DateTime(), nullable=True))

    # listings: demand annotation columns
    with op.batch_alter_table("listings") as batch:
        batch.add_column(sa.Column("demand_score", sa.Float(), nullable=True))
        batch.add_column(sa.Column("found_via_term", sa.String(400), nullable=True))


def downgrade():
    with op.batch_alter_table("source_search_terms") as batch:
        batch.drop_column("last_result_at")
        batch.drop_column("zero_results_streak")
        batch.drop_column("is_baseline")
        batch.drop_column("demand_score")

    with op.batch_alter_table("listings") as batch:
        batch.drop_column("found_via_term")
        batch.drop_column("demand_score")
