"""bot_approval_queue

Revision ID: 20260920_0001
Revises: 20260919_0001
Create Date: 2026-09-20 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260920_0001'
down_revision = '20260919_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ApprovalType enum
    op.execute("""
        CREATE TYPE approvaltype AS ENUM (
            'photo_pack', 'model_3d', 'playbook', 'prebuilt', 'pricing'
        )
    """)
    
    # Create ApprovalStatus enum
    op.execute("""
        CREATE TYPE approvalstatus AS ENUM (
            'pending', 'approved', 'rejected', 'draft'
        )
    """)
    
    # Create bot_approval_queue table
    op.create_table(
        'bot_approval_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('approval_type', sa.Enum('photo_pack', 'model_3d', 'playbook', 'prebuilt', 'pricing', name='approvaltype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'draft', name='approvalstatus'), nullable=False),
        sa.Column('subject_sku', sa.String(length=200), nullable=True),
        sa.Column('subject_category', sa.String(length=50), nullable=True),
        sa.Column('playbook_id', sa.String(length=100), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('sell_price_gbp', sa.Float(), nullable=True),
        sa.Column('total_cost_gbp', sa.Float(), nullable=True),
        sa.Column('est_margin_pct', sa.Float(), nullable=True),
        sa.Column('submitted_by', sa.String(length=100), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_by', sa.String(length=100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_bot_approval_queue_approval_type', 'bot_approval_queue', ['approval_type'])
    op.create_index('ix_bot_approval_queue_status', 'bot_approval_queue', ['status'])
    op.create_index('ix_bot_approval_queue_subject_sku', 'bot_approval_queue', ['subject_sku'])
    op.create_index('ix_bot_approval_queue_playbook_id', 'bot_approval_queue', ['playbook_id'])
    
    # Create playbook_proposals_extended table
    op.create_table(
        'playbook_proposals_extended',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('playbook_id', sa.String(length=100), nullable=False),
        sa.Column('customer_type', sa.String(length=100), nullable=True),
        sa.Column('budget_tier', sa.String(length=50), nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'draft', name='approvalstatus'), nullable=False),
        sa.Column('core_components', sa.JSON(), nullable=False),
        sa.Column('upsells', sa.JSON(), nullable=True),
        sa.Column('allowed_cases', sa.JSON(), nullable=True),
        sa.Column('sell_price_gbp', sa.Float(), nullable=True),
        sa.Column('total_cost_gbp', sa.Float(), nullable=True),
        sa.Column('est_margin_pct', sa.Float(), nullable=True),
        sa.Column('submitted_by', sa.String(length=100), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_playbook_proposals_extended_playbook_id', 'playbook_proposals_extended', ['playbook_id'])
    
    # Create pricing_proposals table
    op.create_table(
        'pricing_proposals',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.String(length=100), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'draft', name='approvalstatus'), nullable=False),
        sa.Column('sell_price_gbp', sa.Float(), nullable=False),
        sa.Column('total_cost_gbp', sa.Float(), nullable=False),
        sa.Column('est_margin_pct', sa.Float(), nullable=False),
        sa.Column('delivery_buffer_gbp', sa.Float(), nullable=True),
        sa.Column('upsell_delta_sell_gbp', sa.Float(), nullable=True),
        sa.Column('upsell_delta_cost_gbp', sa.Float(), nullable=True),
        sa.Column('pricing_rationale', sa.Text(), nullable=True),
        sa.Column('market_comparison', sa.JSON(), nullable=True),
        sa.Column('submitted_by', sa.String(length=100), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=False),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('ix_pricing_proposals_target_id', 'pricing_proposals', ['target_id'])


def downgrade() -> None:
    op.drop_index('ix_pricing_proposals_target_id', table_name='pricing_proposals')
    op.drop_table('pricing_proposals')
    
    op.drop_index('ix_playbook_proposals_extended_playbook_id', table_name='playbook_proposals_extended')
    op.drop_table('playbook_proposals_extended')
    
    op.drop_index('ix_bot_approval_queue_playbook_id', table_name='bot_approval_queue')
    op.drop_index('ix_bot_approval_queue_subject_sku', table_name='bot_approval_queue')
    op.drop_index('ix_bot_approval_queue_status', table_name='bot_approval_queue')
    op.drop_index('ix_bot_approval_queue_approval_type', table_name='bot_approval_queue')
    op.drop_table('bot_approval_queue')
    
    op.execute('DROP TYPE approvalstatus')
    op.execute('DROP TYPE approvaltype')
