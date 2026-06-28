"""Create orders table

Revision ID: 20260628_0002
Revises: 20260628_0001
Create Date: 2026-06-28 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '20260628_0002'
down_revision = '20260628_0001'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.String(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('specs', sa.JSON(), nullable=False),
        sa.Column('customer_price', sa.Float(), nullable=False),
        sa.Column('component_costs', sa.Float(), nullable=False),
        sa.Column('labor_hours', sa.Float(), server_default='3.0'),
        sa.Column('labor_rate', sa.Float(), server_default='25.0'),
        sa.Column('overhead_amount', sa.Float(), nullable=False),
        sa.Column('profit', sa.Float(), nullable=True),
        sa.Column('promised_delivery_date', sa.DateTime(), nullable=False),
        sa.Column('actual_delivery_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.Enum('awaiting_sourcing', 'parts_ordered', 'building', 'qa', 'ready_to_ship', 'shipped', 'completed', name='orderstatus'), server_default='awaiting_sourcing'),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id')
    )
    op.create_index('ix_orders_order_id', 'orders', ['order_id'])


def downgrade():
    op.drop_index('ix_orders_order_id')
    op.drop_table('orders')
