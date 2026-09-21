"""Add curated_promotions table for dev→prod promotion tracking

Revision ID: 20260921_0002
Revises: 20260921_0001
Create Date: 2026-09-21 11:15:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260921_0002'
down_revision = '20260921_0001'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create curated_promotions table for tracking dev→production promotions.
    
    Records each promotion of approved curated playbooks, pricing, photo packs,
    and 3D assets from dev to production (andromeda-ts).
    """
    op.create_table(
        'curated_promotions',
        sa.Column('id', sa.Integer(), primary_key=True, nullable=False),
        sa.Column('promoted_at', sa.DateTime(), nullable=False),
        sa.Column('promoted_by', sa.String(length=255), nullable=False),
        sa.Column('source_environment', sa.String(length=50), nullable=False, server_default='dev'),
        sa.Column('target_environment', sa.String(length=50), nullable=False, server_default='production'),
        
        sa.Column('promotion_manifest', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        
        sa.Column('playbooks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pricing_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('photo_packs_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('assets_3d_count', sa.Integer(), nullable=False, server_default='0'),
        
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('verification_checks', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        
        sa.Column('import_result', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('import_error', sa.Text(), nullable=True),
        
        sa.Column('rolled_back_at', sa.DateTime(), nullable=True),
        sa.Column('rolled_back_by', sa.String(length=255), nullable=True),
        sa.Column('rollback_reason', sa.Text(), nullable=True),
        
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )
    
    # Create indexes for common queries
    op.create_index('ix_curated_promotions_id', 'curated_promotions', ['id'])
    op.create_index('ix_curated_promotions_promoted_at', 'curated_promotions', ['promoted_at'])
    op.create_index('ix_curated_promotions_status', 'curated_promotions', ['status'])
    op.create_index('ix_curated_promotions_promoted_by', 'curated_promotions', ['promoted_by'])


def downgrade():
    """Remove curated_promotions table."""
    op.drop_index('ix_curated_promotions_promoted_by', table_name='curated_promotions')
    op.drop_index('ix_curated_promotions_status', table_name='curated_promotions')
    op.drop_index('ix_curated_promotions_promoted_at', table_name='curated_promotions')
    op.drop_index('ix_curated_promotions_id', table_name='curated_promotions')
    op.drop_table('curated_promotions')
