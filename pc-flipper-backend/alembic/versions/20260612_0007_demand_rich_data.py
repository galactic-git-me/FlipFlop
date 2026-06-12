"""Add rich demand data tables for Google Trends, Reddit posts, Steam hardware

Revision ID: 20260612_0007
Revises: 20260610_0006
Create Date: 2026-06-12
"""
from alembic import op
import sqlalchemy as sa

revision = "20260612_0007"
down_revision = "20260610_0006"
depends_on = None


def upgrade():
    op.create_table(
        "google_trends_timeseries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query", sa.String(255), nullable=False, index=True),
        sa.Column("topic", sa.String(128), nullable=False, index=True),
        sa.Column("date_label", sa.String(64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False, index=True),
    )

    op.create_table(
        "google_trends_geo",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("query", sa.String(255), nullable=False, index=True),
        sa.Column("topic", sa.String(128), nullable=False),
        sa.Column("region_name", sa.String(128), nullable=False),
        sa.Column("region_code", sa.String(32), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False, index=True),
    )

    op.create_table(
        "reddit_posts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reddit_id", sa.String(32), nullable=False, index=True),
        sa.Column("query", sa.String(255), nullable=False, index=True),
        sa.Column("topic", sa.String(128), nullable=False, index=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("subreddit", sa.String(128), nullable=False, index=True),
        sa.Column("post_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("num_comments", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("permalink", sa.Text(), nullable=True),
        sa.Column("created_utc", sa.DateTime(), nullable=False),
        sa.Column("collected_at", sa.DateTime(), nullable=False, index=True),
        sa.UniqueConstraint("reddit_id", name="uq_reddit_post_id"),
    )

    op.create_table(
        "steam_hardware_stats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(64), nullable=False, index=True),
        sa.Column("item_name", sa.String(255), nullable=False),
        sa.Column("percentage", sa.Float(), nullable=False),
        sa.Column("change_pct", sa.Float(), nullable=True),
        sa.Column("collected_at", sa.DateTime(), nullable=False, index=True),
    )


def downgrade():
    op.drop_table("steam_hardware_stats")
    op.drop_table("reddit_posts")
    op.drop_table("google_trends_geo")
    op.drop_table("google_trends_timeseries")
