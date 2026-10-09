"""bot_approval_queue

Revision ID: 20260920_0001
Revises: 20260919_0001
Create Date: 2026-09-20 17:00:00.000000

"""
from alembic import op


revision = "20260920_0001"
down_revision = "20260919_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE approvaltype AS ENUM (
                'photo_pack', 'model_3d', 'playbook', 'prebuilt', 'pricing'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE approvalstatus AS ENUM (
                'pending', 'approved', 'rejected', 'draft'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS bot_approval_queue (
            id SERIAL PRIMARY KEY,
            approval_type approvaltype NOT NULL,
            status approvalstatus NOT NULL,
            subject_sku VARCHAR(200),
            subject_category VARCHAR(50),
            playbook_id VARCHAR(100),
            payload JSON NOT NULL,
            sell_price_gbp FLOAT,
            total_cost_gbp FLOAT,
            est_margin_pct FLOAT,
            submitted_by VARCHAR(100),
            submitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            reviewed_by VARCHAR(100),
            reviewed_at TIMESTAMP WITHOUT TIME ZONE,
            rejection_reason TEXT,
            notes TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_bot_approval_queue_approval_type ON bot_approval_queue (approval_type);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bot_approval_queue_status ON bot_approval_queue (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bot_approval_queue_subject_sku ON bot_approval_queue (subject_sku);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bot_approval_queue_playbook_id ON bot_approval_queue (playbook_id);")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS playbook_proposals_extended (
            id SERIAL PRIMARY KEY,
            playbook_id VARCHAR(100) NOT NULL,
            customer_type VARCHAR(100),
            budget_tier VARCHAR(50),
            status approvalstatus NOT NULL,
            core_components JSON NOT NULL,
            upsells JSON,
            allowed_cases JSON,
            sell_price_gbp FLOAT,
            total_cost_gbp FLOAT,
            est_margin_pct FLOAT,
            submitted_by VARCHAR(100),
            submitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            approved_by VARCHAR(100),
            approved_at TIMESTAMP WITHOUT TIME ZONE,
            rejection_reason TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_playbook_proposals_extended_playbook_id ON playbook_proposals_extended (playbook_id);")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pricing_proposals (
            id SERIAL PRIMARY KEY,
            target_type VARCHAR(50) NOT NULL,
            target_id VARCHAR(100) NOT NULL,
            status approvalstatus NOT NULL,
            sell_price_gbp FLOAT NOT NULL,
            total_cost_gbp FLOAT NOT NULL,
            est_margin_pct FLOAT NOT NULL,
            delivery_buffer_gbp FLOAT,
            upsell_delta_sell_gbp FLOAT,
            upsell_delta_cost_gbp FLOAT,
            pricing_rationale TEXT,
            market_comparison JSON,
            submitted_by VARCHAR(100),
            submitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            approved_by VARCHAR(100),
            approved_at TIMESTAMP WITHOUT TIME ZONE,
            rejection_reason TEXT,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE
        );
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_pricing_proposals_target_id ON pricing_proposals (target_id);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pricing_proposals;")
    op.execute("DROP TABLE IF EXISTS playbook_proposals_extended;")
    op.execute("DROP TABLE IF EXISTS bot_approval_queue;")
    op.execute("DROP TYPE IF EXISTS approvalstatus;")
    op.execute("DROP TYPE IF EXISTS approvaltype;")
