"""Create demand_events table

Revision ID: 20260628_0005
Revises: 20260628_0004
Create Date: 2026-06-28 00:00:04.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260628_0005'
down_revision = '20260628_0004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'demand_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('budget_chosen', sa.String(), nullable=False),
        sa.Column('use_case', sa.String(), nullable=True),
        sa.Column('specs', sa.JSON(), nullable=False),
        sa.Column('quote_generated', sa.Boolean(), server_default='false'),
        sa.Column('converted_to_order', sa.Boolean(), server_default='false'),
        sa.Column('time_spent_minutes', sa.Integer(), server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_demand_events_session_id', 'demand_events', ['session_id'])


def downgrade():
    op.drop_index('ix_demand_events_session_id')
    op.drop_table('demand_events')
