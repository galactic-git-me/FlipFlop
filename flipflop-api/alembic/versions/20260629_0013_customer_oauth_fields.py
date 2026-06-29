"""Add OAuth fields to customers table (Google and GitHub)

Revision ID: 20260629_0013
Revises: 20260629_0012
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa

revision = "20260629_0013"
down_revision = "20260629_0012"
depends_on = None


def upgrade():
    # Add OAuth provider fields to customers table
    op.add_column('customers', sa.Column('google_id', sa.String(255), unique=True, nullable=True, index=True))
    op.add_column('customers', sa.Column('google_email', sa.String(255), nullable=True))
    op.add_column('customers', sa.Column('github_id', sa.Integer(), unique=True, nullable=True, index=True))
    op.add_column('customers', sa.Column('github_username', sa.String(255), nullable=True))
    op.add_column('customers', sa.Column('oauth_provider', sa.String(50), nullable=True))


def downgrade():
    op.drop_column('customers', 'oauth_provider')
    op.drop_column('customers', 'github_username')
    op.drop_column('customers', 'github_id')
    op.drop_column('customers', 'google_email')
    op.drop_column('customers', 'google_id')
