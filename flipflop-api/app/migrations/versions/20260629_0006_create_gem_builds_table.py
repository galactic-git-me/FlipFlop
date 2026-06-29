"""Create gem_builds table for speculative inventory recommendations

Revision ID: 20260629_0006
Revises: 20260628_0005
Create Date: 2026-06-29 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260629_0006'
down_revision = '20260628_0005'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'gem_builds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('use_case', sa.String(100), nullable=False),
        sa.Column('target_budget_gbp', sa.Float(), nullable=False),
        sa.Column('specs', sa.JSON(), nullable=False),
        sa.Column('estimated_cost_to_build', sa.Float(), nullable=False),
        sa.Column('estimated_market_price', sa.Float(), nullable=False),
        sa.Column('margin_gbp', sa.Float(), nullable=False),
        sa.Column('margin_percent', sa.Float(), nullable=False),
        sa.Column('confidence_score', sa.Integer(), nullable=False),
        sa.Column('risk_level', sa.Enum('low', 'medium', 'high', name='gemrisklevel'), nullable=False),
        sa.Column('recommended_quantity', sa.Integer(), nullable=False),
        sa.Column('reasoning', sa.String(1000), nullable=False),
        sa.Column('cost_breakdown', sa.JSON(), nullable=False),
        sa.Column('analysis_period_days', sa.Integer(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_gem_builds_name', 'gem_builds', ['name'])
    op.create_index('ix_gem_builds_use_case', 'gem_builds', ['use_case'])


def downgrade():
    op.drop_index('ix_gem_builds_use_case')
    op.drop_index('ix_gem_builds_name')
    op.drop_table('gem_builds')
