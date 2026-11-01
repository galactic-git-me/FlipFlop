"""Persistent Codex Chrome jobs and confirmed channel URLs."""

from alembic import op
import sqlalchemy as sa

revision = "20261030_0001"
down_revision = "20261028_0001"
branch_labels = None
depends_on = None


def _ensure_column(bind, table, column):
    names = {item["name"] for item in sa.inspect(bind).get_columns(table)}
    if column.name not in names:
        op.add_column(table, column)


def _ensure_job_table(bind):
    tables = set(sa.inspect(bind).get_table_names())
    if "browser_listing_jobs" not in tables:
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
            sa.Column(
                "attempt_count", sa.Integer(), nullable=False, server_default="0"
            ),
            sa.Column(
                "available_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column("message", sa.String(500)),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    else:
        _ensure_column(
            bind,
            "browser_listing_jobs",
            sa.Column(
                "attempt_count", sa.Integer(), nullable=False, server_default="0"
            ),
        )
        names = {
            item["name"]
            for item in sa.inspect(bind).get_columns("browser_listing_jobs")
        }
        if "available_at" not in names:
            op.add_column(
                "browser_listing_jobs",
                sa.Column("available_at", sa.DateTime(), nullable=True),
            )
            op.execute(
                sa.text(
                    "UPDATE browser_listing_jobs SET available_at = COALESCE(available_at, created_at, CURRENT_TIMESTAMP)"
                )
            )
            with op.batch_alter_table("browser_listing_jobs") as batch:
                batch.alter_column(
                    "available_at", existing_type=sa.DateTime(), nullable=False
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


def upgrade():
    bind = op.get_bind()
    if "channel_listings" not in set(sa.inspect(bind).get_table_names()):
        raise RuntimeError("channel_listings must exist before browser listing jobs")
    _ensure_column(
        bind,
        "channel_listings",
        sa.Column("listing_url", sa.String(1000), nullable=True),
    )
    _ensure_column(
        bind,
        "channel_listings",
        sa.Column("last_payload_hash", sa.String(64), nullable=True),
    )
    _ensure_column(
        bind,
        "channel_listings",
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
    )
    _ensure_job_table(bind)


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
    for name in ("last_checked_at", "last_payload_hash", "listing_url"):
        if name in columns:
            op.drop_column("channel_listings", name)
