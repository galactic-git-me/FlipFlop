"""Add curated_builds table for admin-managed pre-designed PC builds.

Revision ID: 20260920_0001
Revises: 20260915_0001
Create Date: 2026-09-20
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260920_0001"
down_revision = "20260915_0001"
depends_on = None


def upgrade():
    op.create_table(
        'curated_builds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('definition_id', sa.String(length=50), nullable=False),
        sa.Column('segment', sa.String(length=100), nullable=False),
        sa.Column('tier', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('use', sa.Text(), nullable=False),
        sa.Column('components', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('estimated_price_gbp', sa.Float(), nullable=True),
        sa.Column('components_cost', sa.Float(), nullable=True),
        sa.Column('markup_percentage', sa.Float(), nullable=False, server_default='25.0'),
        sa.Column('is_published', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_featured', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_available', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('availability_notes', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_curated_builds_definition_id', 'curated_builds', ['definition_id'], unique=True)
    op.create_index('ix_curated_builds_segment', 'curated_builds', ['segment'])
    op.create_index('ix_curated_builds_tier', 'curated_builds', ['tier'])
    op.create_index('ix_curated_builds_is_published', 'curated_builds', ['is_published'])
    op.create_index('ix_curated_builds_created_at', 'curated_builds', ['created_at'])


def downgrade():
    op.drop_index('ix_curated_builds_created_at', table_name='curated_builds')
    op.drop_index('ix_curated_builds_is_published', table_name='curated_builds')
    op.drop_index('ix_curated_builds_tier', table_name='curated_builds')
    op.drop_index('ix_curated_builds_segment', table_name='curated_builds')
    op.drop_index('ix_curated_builds_definition_id', table_name='curated_builds')
    op.drop_table('curated_builds')
