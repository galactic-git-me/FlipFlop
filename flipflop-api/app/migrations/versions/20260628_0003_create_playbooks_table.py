"""Create playbooks table

Revision ID: 20260628_0003
Revises: 20260628_0002
Create Date: 2026-06-28 00:00:02.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260628_0003'
down_revision = '20260628_0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'playbooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('target_budget', sa.Float(), nullable=False),
        sa.Column('target_use_case', sa.String(), nullable=True),
        sa.Column('specs', sa.JSON(), nullable=False),
        sa.Column('historical_demand_pct', sa.Float(), server_default='0.0'),
        sa.Column('historical_margin_avg', sa.Float(), server_default='0.0'),
        sa.Column('avg_days_to_sell', sa.Float(), server_default='0.0'),
        sa.Column('market_selling_price', sa.Float(), nullable=True),
        sa.Column('used_market_price', sa.Float(), nullable=True),
        sa.Column('status', sa.Enum('active', 'deprecated', 'retired', name='playbookstatus'), server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('ix_playbooks_name', 'playbooks', ['name'])


def downgrade():
    op.drop_index('ix_playbooks_name')
    op.drop_table('playbooks')
