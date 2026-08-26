"""Block hard deletion of manual builds and retain an audit trail.

Revision ID: 20260826_0016
Revises: 20260826_0015
"""
from alembic import op

revision = "20260826_0016"
down_revision = "20260826_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS manual_build_deletion_audit (
            id BIGSERIAL PRIMARY KEY,
            manual_build_id INTEGER NOT NULL,
            build_name TEXT,
            action VARCHAR(30) NOT NULL,
            attempted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            database_user TEXT NOT NULL DEFAULT current_user,
            application_name TEXT DEFAULT current_setting('application_name', true),
            client_address TEXT DEFAULT inet_client_addr()::text,
            row_snapshot JSONB NOT NULL
        )
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION protect_manual_build_from_delete()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO manual_build_deletion_audit
                (manual_build_id, build_name, action, row_snapshot)
            VALUES (OLD.id, OLD.name, 'hard_delete_blocked', to_jsonb(OLD));
            RAISE WARNING 'Blocked hard deletion of manual build % (%)', OLD.id, OLD.name;
            RETURN NULL;
        END;
        $$
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_protect_manual_build_delete ON manual_builds")
    op.execute("""
        CREATE TRIGGER trg_protect_manual_build_delete BEFORE DELETE ON manual_builds
        FOR EACH ROW EXECUTE FUNCTION protect_manual_build_from_delete()
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION audit_manual_build_archive()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.is_archived IS DISTINCT FROM NEW.is_archived THEN
                INSERT INTO manual_build_deletion_audit
                    (manual_build_id, build_name, action, row_snapshot)
                VALUES (NEW.id, NEW.name,
                    CASE WHEN NEW.is_archived THEN 'archived' ELSE 'restored' END,
                    to_jsonb(NEW));
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("DROP TRIGGER IF EXISTS trg_audit_manual_build_archive ON manual_builds")
    op.execute("""
        CREATE TRIGGER trg_audit_manual_build_archive AFTER UPDATE OF is_archived ON manual_builds
        FOR EACH ROW EXECUTE FUNCTION audit_manual_build_archive()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_manual_build_archive ON manual_builds")
    op.execute("DROP FUNCTION IF EXISTS audit_manual_build_archive()")
    op.execute("DROP TRIGGER IF EXISTS trg_protect_manual_build_delete ON manual_builds")
    op.execute("DROP FUNCTION IF EXISTS protect_manual_build_from_delete()")
    op.execute("DROP TABLE IF EXISTS manual_build_deletion_audit")
