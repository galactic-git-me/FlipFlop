"""add compliant market ingestion tables

Revision ID: 20260518_0002
Revises: 20260517_0001
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "20260518_0002"
down_revision = "20260517_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("records_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_inserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
    )
    op.create_index("ix_source_runs_source", "source_runs", ["source"])
    op.create_index("ix_source_runs_status", "source_runs", ["status"])
    op.create_index("ix_source_runs_started_at", "source_runs", ["started_at"])

    op.create_table(
        "listings_raw",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("source", "external_id", name="uq_listings_raw_source_external_id"),
    )
    op.create_index("ix_listings_raw_source", "listings_raw", ["source"])
    op.create_index("ix_listings_raw_external_id", "listings_raw", ["external_id"])
    op.create_index("ix_listings_raw_ingested_at", "listings_raw", ["ingested_at"])

    op.create_table(
        "listings_normalized",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("location_text", sa.String(length=200), nullable=True),
        sa.Column("category", sa.String(length=120), nullable=True),
        sa.Column("condition", sa.String(length=80), nullable=True),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("seller_type", sa.String(length=80), nullable=True),
        sa.Column("listed_at", sa.DateTime(), nullable=True),
        sa.Column("dedupe_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("source", "external_id", name="uq_listings_norm_source_external_id"),
    )
    op.create_index("ix_listings_norm_source", "listings_normalized", ["source"])
    op.create_index("ix_listings_norm_external_id", "listings_normalized", ["external_id"])
    op.create_index("ix_listings_norm_dedupe_fingerprint", "listings_normalized", ["dedupe_fingerprint"])
    op.create_index("ix_listings_norm_last_seen_at", "listings_normalized", ["last_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_listings_norm_last_seen_at", table_name="listings_normalized")
    op.drop_index("ix_listings_norm_dedupe_fingerprint", table_name="listings_normalized")
    op.drop_index("ix_listings_norm_external_id", table_name="listings_normalized")
    op.drop_index("ix_listings_norm_source", table_name="listings_normalized")
    op.drop_table("listings_normalized")

    op.drop_index("ix_listings_raw_ingested_at", table_name="listings_raw")
    op.drop_index("ix_listings_raw_external_id", table_name="listings_raw")
    op.drop_index("ix_listings_raw_source", table_name="listings_raw")
    op.drop_table("listings_raw")

    op.drop_index("ix_source_runs_started_at", table_name="source_runs")
    op.drop_index("ix_source_runs_status", table_name="source_runs")
    op.drop_index("ix_source_runs_source", table_name="source_runs")
    op.drop_table("source_runs")

