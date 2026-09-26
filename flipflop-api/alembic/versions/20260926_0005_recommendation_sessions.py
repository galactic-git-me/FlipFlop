"""Persist replayable requirements and envelope decisions.

Revision ID: vnext_20260926_05
Revises: cb_20260926_04_obs_tags
"""
from alembic import op
import sqlalchemy as sa

revision = "vnext_20260926_05"
down_revision = "cb_20260926_04_obs_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recommendation_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rules_version", sa.String(length=20), nullable=False),
        sa.Column("requirements_json", sa.JSON(), nullable=False),
        sa.Column("envelope_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("recommendation_sessions")
