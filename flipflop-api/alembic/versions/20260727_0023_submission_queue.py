"""Create submission_queue table for async gem-radar processing.

Revision ID: 20260727_0023
Revises: 20260723_0022
Create Date: 2026-07-27
"""
from alembic import op
import sqlalchemy as sa

revision = "20260727_0023"
down_revision = "20260723_0022"
depends_on = None


def upgrade():
    op.create_table(
        "submission_queue",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("search_run_id", sa.String(255), nullable=False),
        sa.Column("search_id", sa.String(255), nullable=False),
        sa.Column("query", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("max_candidates_for_deep_research", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("listings_json", sa.JSON(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("first_attempt_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_submission_queue_status", "submission_queue", ["status"])
    op.create_index("ix_submission_queue_created_at", "submission_queue", ["created_at"])
    op.create_index("ix_submission_queue_search_run_id", "submission_queue", ["search_run_id"])


def downgrade():
    op.drop_index("ix_submission_queue_search_run_id", table_name="submission_queue")
    op.drop_index("ix_submission_queue_created_at", table_name="submission_queue")
    op.drop_index("ix_submission_queue_status", table_name="submission_queue")
    op.drop_table("submission_queue")
