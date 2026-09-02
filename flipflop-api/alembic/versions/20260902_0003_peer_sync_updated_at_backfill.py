"""Add updated_at to tables the peer synchroniser needs it on.

order_photos, inventory_events, and the gem_radar_* observation/scan/scored
tables previously had no updated_at column, so app.services.peer_sync
correctly refused to sync them. Backfills from each table's existing
timestamp column so no row looks artificially "just changed".
"""

from alembic import op

revision = "20260902_0003"
down_revision = "20260902_0002"
branch_labels = None
depends_on = None

_TABLES = (
    ("order_photos", "created_at"),
    ("inventory_events", "created_at"),
    ("gem_radar_scan_runs", "occurred_at"),
    ("gem_radar_listing_observations", "observed_at"),
    ("gem_radar_scored_listings", "scored_at"),
    ("gem_radar_sold_observations", "observed_at"),
    ("gem_radar_amazon_observations", "observed_at"),
)


def upgrade() -> None:
    for table, source_col in _TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")
        op.execute(f"UPDATE {table} SET updated_at = COALESCE({source_col}, now()) WHERE updated_at IS NULL")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN updated_at SET DEFAULT now()")
        op.execute(f"ALTER TABLE {table} ALTER COLUMN updated_at SET NOT NULL")


def downgrade() -> None:
    for table, _source_col in _TABLES:
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS updated_at")
