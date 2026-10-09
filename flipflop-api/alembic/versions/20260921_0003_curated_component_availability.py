"""Add curated component availability tables (primary + backup SKUs)

Revision ID: 20260921_0003
Revises: 20260921_0002
Create Date: 2026-09-21 11:20:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260921_0003'
down_revision = '20260921_0002'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create tables for curated component availability management:
    - curated_component_skus (primary + backup SKUs)
    - curated_build_availability (overall build availability)
    - sku_swap_events (audit trail for SKU swaps)
    """
    
    # Create curated_component_skus table
    op.create_table(
        'curated_component_skus',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('curated_build_id', sa.String(length=50), nullable=False),
        sa.Column('component_slot', sa.String(length=50), nullable=False),
        
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        
        sa.Column('component_title', sa.String(length=500), nullable=False),
        sa.Column('component_spec', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        sa.Column('preferred_vendor', sa.String(length=100), nullable=True),
        sa.Column('vendor_sku', sa.String(length=255), nullable=True),
        sa.Column('vendor_url', sa.String(length=1000), nullable=True),
        
        sa.Column('target_cost_gbp', sa.Float(), nullable=True),
        sa.Column('approved_cost_gbp', sa.Float(), nullable=True),
        
        sa.Column('availability_status', sa.String(length=50), nullable=False, server_default='unknown'),
        sa.Column('availability_checked_at', sa.DateTime(), nullable=True),
        sa.Column('availability_check_source', sa.String(length=100), nullable=True),
        
        sa.Column('estimated_stock_level', sa.Integer(), nullable=True),
        sa.Column('low_stock_threshold', sa.Integer(), nullable=False, server_default='5'),
        
        sa.Column('compatibility_notes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('requires_approval_for_swap', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('requires_remesh', sa.Boolean(), nullable=False, server_default='false'),
        
        sa.Column('bot_approval_queue_id', sa.Integer(), nullable=True),
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('deactivated_at', sa.DateTime(), nullable=True),
        sa.Column('deactivation_reason', sa.String(length=500), nullable=True),
        
        sa.Column('notes', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create indexes for curated_component_skus
    op.create_index('ix_curated_component_skus_id', 'curated_component_skus', ['id'])
    op.create_index('ix_curated_component_skus_build_id', 'curated_component_skus', ['curated_build_id'])
    op.create_index('ix_curated_component_skus_build_slot', 'curated_component_skus', ['curated_build_id', 'component_slot'])
    op.create_index('ix_curated_component_skus_build_slot_priority', 'curated_component_skus', ['curated_build_id', 'component_slot', 'priority'])
    op.create_index('ix_curated_component_skus_active', 'curated_component_skus', ['is_active'])
    op.create_index('ix_curated_component_skus_availability', 'curated_component_skus', ['availability_status'])
    
    # Create curated_build_availability table
    op.create_table(
        'curated_build_availability',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('curated_build_id', sa.String(length=50), unique=True, nullable=False),
        
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('availability_status', sa.String(length=50), nullable=False, server_default='available'),
        
        sa.Column('components_status', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('active_skus', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        sa.Column('using_backup_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('backup_slots', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),
        sa.Column('last_check_source', sa.String(length=100), nullable=True),
        sa.Column('next_check_due_at', sa.DateTime(), nullable=True),
        
        sa.Column('is_visible_on_shop', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('hidden_reason', sa.String(length=500), nullable=True),
        
        sa.Column('sku_swap_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_sku_swap_at', sa.DateTime(), nullable=True),
        
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create indexes for curated_build_availability
    op.create_index('ix_curated_build_availability_id', 'curated_build_availability', ['id'])
    op.create_index('ix_curated_build_availability_build_id', 'curated_build_availability', ['curated_build_id'])
    op.create_index('ix_curated_build_availability_is_available', 'curated_build_availability', ['is_available'])
    op.create_index('ix_curated_build_availability_visible', 'curated_build_availability', ['is_visible_on_shop'])
    
    # Create sku_swap_events table
    op.create_table(
        'sku_swap_events',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('curated_build_id', sa.String(length=50), nullable=False),
        sa.Column('component_slot', sa.String(length=50), nullable=False),
        
        sa.Column('from_sku_id', sa.Integer(), sa.ForeignKey('curated_component_skus.id'), nullable=True),
        sa.Column('to_sku_id', sa.Integer(), sa.ForeignKey('curated_component_skus.id'), nullable=False),
        
        sa.Column('swap_reason', sa.String(length=100), nullable=False),
        sa.Column('swap_source', sa.String(length=100), nullable=False, server_default='system'),
        
        sa.Column('availability_status_before', sa.String(length=50), nullable=True),
        sa.Column('availability_status_after', sa.String(length=50), nullable=True),
        
        sa.Column('triggered_by_order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=True),
        
        sa.Column('approved_by', sa.String(length=255), nullable=True),
        
        sa.Column('swapped_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create indexes for sku_swap_events
    op.create_index('ix_sku_swap_events_id', 'sku_swap_events', ['id'])
    op.create_index('ix_sku_swap_events_build_id', 'sku_swap_events', ['curated_build_id'])
    op.create_index('ix_sku_swap_events_swapped_at', 'sku_swap_events', ['swapped_at'])
    op.create_index('ix_sku_swap_events_order_id', 'sku_swap_events', ['triggered_by_order_id'])


def downgrade():
    """Remove curated component availability tables."""
    # Drop indexes
    op.drop_index('ix_sku_swap_events_order_id', table_name='sku_swap_events')
    op.drop_index('ix_sku_swap_events_swapped_at', table_name='sku_swap_events')
    op.drop_index('ix_sku_swap_events_build_id', table_name='sku_swap_events')
    op.drop_index('ix_sku_swap_events_id', table_name='sku_swap_events')
    
    op.drop_index('ix_curated_build_availability_visible', table_name='curated_build_availability')
    op.drop_index('ix_curated_build_availability_is_available', table_name='curated_build_availability')
    op.drop_index('ix_curated_build_availability_build_id', table_name='curated_build_availability')
    op.drop_index('ix_curated_build_availability_id', table_name='curated_build_availability')
    
    op.drop_index('ix_curated_component_skus_availability', table_name='curated_component_skus')
    op.drop_index('ix_curated_component_skus_active', table_name='curated_component_skus')
    op.drop_index('ix_curated_component_skus_build_slot_priority', table_name='curated_component_skus')
    op.drop_index('ix_curated_component_skus_build_slot', table_name='curated_component_skus')
    op.drop_index('ix_curated_component_skus_build_id', table_name='curated_component_skus')
    op.drop_index('ix_curated_component_skus_id', table_name='curated_component_skus')
    
    # Drop tables (in reverse order due to foreign keys)
    op.drop_table('sku_swap_events')
    op.drop_table('curated_build_availability')
    op.drop_table('curated_component_skus')
