"""Persistent Codex Chrome jobs and confirmed channel URLs."""
from alembic import op
import sqlalchemy as sa

revision = "20261030_0001"
down_revision = "20261028_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("channel_listings", sa.Column("listing_url", sa.String(1000), nullable=True))
    op.add_column("channel_listings", sa.Column("last_payload_hash", sa.String(64), nullable=True))
    op.add_column("channel_listings", sa.Column("last_checked_at", sa.DateTime(), nullable=True))
    op.create_table("browser_listing_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel_listing_id", sa.Integer(), sa.ForeignKey("channel_listings.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("lease_token", sa.String(64)), sa.Column("lease_until", sa.DateTime()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("message", sa.String(500)),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("uq_browser_listing_job_pending", "browser_listing_jobs", ["channel_listing_id"], unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running', 'blocked', 'needs_review')"))


def downgrade():
    op.drop_table("browser_listing_jobs")
    op.drop_column("channel_listings", "listing_url")
    op.drop_column("channel_listings", "last_payload_hash")
    op.drop_column("channel_listings", "last_checked_at")
