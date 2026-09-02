"""Add delete-tombstone and run/health durability to the peer synchroniser."""

from alembic import op

revision = "20260902_0002"
down_revision = "20260902_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE peer_sync_state ADD COLUMN IF NOT EXISTS row_checksum TEXT")
    op.execute("""CREATE TABLE IF NOT EXISTS peer_sync_tombstones (
        id BIGSERIAL PRIMARY KEY, table_name TEXT NOT NULL, row_key TEXT NOT NULL,
        node TEXT NOT NULL, detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        applied_at TIMESTAMPTZ,
        UNIQUE (table_name, row_key, node, detected_at))""")
    op.execute("""CREATE TABLE IF NOT EXISTS peer_sync_runs (
        id BIGSERIAL PRIMARY KEY, node TEXT NOT NULL,
        started_at TIMESTAMPTZ NOT NULL DEFAULT now(), finished_at TIMESTAMPTZ,
        status TEXT NOT NULL DEFAULT 'running',
        tables_synced INTEGER NOT NULL DEFAULT 0, copied INTEGER NOT NULL DEFAULT 0,
        skipped INTEGER NOT NULL DEFAULT 0, conflicts INTEGER NOT NULL DEFAULT 0,
        deletes INTEGER NOT NULL DEFAULT 0, errors_count INTEGER NOT NULL DEFAULT 0,
        error_detail TEXT)""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS peer_sync_runs")
    op.execute("DROP TABLE IF EXISTS peer_sync_tombstones")
    op.execute("ALTER TABLE peer_sync_state DROP COLUMN IF EXISTS row_checksum")
