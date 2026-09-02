"""Add metadata tables used by the explicit peer synchroniser."""

from alembic import op

revision = "20260902_0001"
down_revision = "20260827_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE TABLE IF NOT EXISTS peer_sync_state (
        table_name TEXT NOT NULL, row_key TEXT NOT NULL, source_node TEXT NOT NULL,
        source_updated_at TIMESTAMPTZ NOT NULL, synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (table_name, row_key))""")
    op.execute("""CREATE TABLE IF NOT EXISTS peer_sync_conflicts (
        id BIGSERIAL PRIMARY KEY, table_name TEXT NOT NULL, row_key TEXT NOT NULL,
        local_updated_at TIMESTAMPTZ, remote_updated_at TIMESTAMPTZ, winner TEXT NOT NULL,
        detected_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS peer_sync_conflicts")
    op.execute("DROP TABLE IF EXISTS peer_sync_state")
