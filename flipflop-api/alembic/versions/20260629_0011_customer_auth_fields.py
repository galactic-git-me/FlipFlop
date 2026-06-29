"""Add password_hash and last_login fields to customers table

Revision ID: 20260629_0011
Revises: 20260627_0010
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260629_0011"
down_revision = "20260627_0010"
depends_on = None


def upgrade():
    # Check if customers table exists, if not create it with all fields
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('address', sa.String(500)),
        sa.Column('phone', sa.String(20)),
        sa.Column('last_login', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Index('idx_customers_email', 'email'),
    )


def downgrade():
    op.drop_table('customers')
