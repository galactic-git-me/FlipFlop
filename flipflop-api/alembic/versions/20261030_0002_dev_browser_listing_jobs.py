"""Legacy Dev browser-listing schema head retained for safe upgrades."""

from alembic import op
import sqlalchemy as sa

revision = "20261030_dev_browser"
down_revision = "20261012_merge_heads"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "channel_listings" not in tables:
        raise RuntimeError("channel_listings must exist before browser listing jobs")
    columns = {
        item["name"] for item in sa.inspect(bind).get_columns("channel_listings")
    }
    if "listing_url" not in columns:
        op.add_column(
            "channel_listings", sa.Column("listing_url", sa.String(1000), nullable=True)
        )
    if "browser_listing_jobs" not in set(sa.inspect(bind).get_table_names()):
        op.create_table(
            "browser_listing_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "channel_listing_id",
                sa.Integer(),
                sa.ForeignKey("channel_listings.id"),
                nullable=False,
            ),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("operation", sa.String(20), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("lease_token", sa.String(64)),
            sa.Column("lease_until", sa.DateTime()),
            sa.Column("message", sa.String(500)),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    indexes = {
        item["name"] for item in sa.inspect(bind).get_indexes("browser_listing_jobs")
    }
    if "uq_browser_listing_job_pending" not in indexes:
        op.create_index(
            "uq_browser_listing_job_pending",
            "browser_listing_jobs",
            ["channel_listing_id"],
            unique=True,
            postgresql_where=sa.text(
                "status IN ('queued', 'running', 'blocked', 'needs_review')"
            ),
            sqlite_where=sa.text(
                "status IN ('queued', 'running', 'blocked', 'needs_review')"
            ),
        )


def downgrade():
    bind = op.get_bind()
    if "browser_listing_jobs" in set(sa.inspect(bind).get_table_names()):
        if any(
            item["name"] == "uq_browser_listing_job_pending"
            for item in sa.inspect(bind).get_indexes("browser_listing_jobs")
        ):
            op.drop_index(
                "uq_browser_listing_job_pending", table_name="browser_listing_jobs"
            )
        op.drop_table("browser_listing_jobs")
    columns = {
        item["name"] for item in sa.inspect(bind).get_columns("channel_listings")
    }
    if "listing_url" in columns:
        op.drop_column("channel_listings", "listing_url")
