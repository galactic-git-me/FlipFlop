"""Add PC-case slots to every catalogue playbook."""
from alembic import op


revision = "20260916_0002"
down_revision = "20260916_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        INSERT INTO playbook_slots
            (playbook_id, slot_type, is_customer_visible, tier_names,
             score_band_budget, score_band_mid, score_band_high,
             created_at, updated_at)
        SELECT id, 'case', true,
               '{\"budget\": \"Budget Case\", \"mid\": \"Mid-Range Case\", \"high\": \"High-End Case\"}'::json,
               '[40, 65]'::json, '[65, 80]'::json, '[80, 100]'::json,
               CURRENT_TIMESTAMP::text, CURRENT_TIMESTAMP::text
        FROM playbooks
        ON CONFLICT (playbook_id, slot_type) DO NOTHING
    """)


def downgrade() -> None:
    op.execute("DELETE FROM playbook_slots WHERE slot_type = 'case'")
