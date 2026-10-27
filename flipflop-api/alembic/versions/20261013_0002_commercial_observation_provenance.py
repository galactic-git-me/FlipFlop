"""Preserve commercial evidence independently of lightweight sightings.

Revision ID: 20261013_0002
Revises: 20261013_0001
"""
from alembic import op
import sqlalchemy as sa

revision = '20261013_0002'
down_revision = '20261013_0001'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('gem_radar_listing_observations', sa.Column('commercial_source_evidence', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('gem_radar_listing_observations', 'commercial_source_evidence')
