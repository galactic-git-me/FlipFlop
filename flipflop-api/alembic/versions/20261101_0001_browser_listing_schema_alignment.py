"""Reconcile browser-listing columns across the former Dev and Prod heads."""

from alembic import op
import sqlalchemy as sa

revision = "20261101_0001"
down_revision = "20261031_0002"
branch_labels = None
depends_on = None


def _ensure_column(bind, table, column):
    names = {item["name"] for item in sa.inspect(bind).get_columns(table)}
    if column.name not in names:
        op.add_column(table, column)


def upgrade():
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "channel_listings" not in tables or "browser_listing_jobs" not in tables:
        raise RuntimeError(
            "Browser listing base schema is missing; apply its parent migrations first"
        )

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

    _ensure_column(
        bind,
        "browser_listing_jobs",
        sa.Column("attempt_count", sa.Integer(), nullable=True, server_default="0"),
    )
    job_columns = {
        item["name"] for item in sa.inspect(bind).get_columns("browser_listing_jobs")
    }
    if "available_at" not in job_columns:
        op.add_column(
            "browser_listing_jobs",
            sa.Column("available_at", sa.DateTime(), nullable=True),
        )
    op.execute(
        sa.text(
            "UPDATE browser_listing_jobs SET attempt_count = COALESCE(attempt_count, 0), available_at = COALESCE(available_at, created_at, CURRENT_TIMESTAMP)"
        )
    )
    with op.batch_alter_table("browser_listing_jobs") as batch:
        batch.alter_column(
            "attempt_count",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )
        batch.alter_column("available_at", existing_type=sa.DateTime(), nullable=False)

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
    # Keep the reconciled nullable-safe schema in place; reversing it could
    # discard the only saved browser payload/check timestamps for old Dev rows.
    pass
