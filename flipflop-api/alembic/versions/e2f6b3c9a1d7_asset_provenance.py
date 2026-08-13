"""add provenance fields to component_3d_assets

Revision ID: e2f6b3c9a1d7
Revises: d1e5f7a2b8c3
Create Date: 2026-08-12 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2f6b3c9a1d7'
down_revision: Union[str, None] = 'd1e5f7a2b8c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('component_3d_assets', sa.Column('provenance_status', sa.String(length=30), nullable=False, server_default='metadata-only'))
    op.add_column('component_3d_assets', sa.Column('source_name', sa.String(length=200), nullable=True))
    op.add_column('component_3d_assets', sa.Column('source_url', sa.String(length=1000), nullable=True))
    op.add_column('component_3d_assets', sa.Column('licence', sa.String(length=200), nullable=True))
    op.add_column('component_3d_assets', sa.Column('licence_url', sa.String(length=1000), nullable=True))
    op.add_column('component_3d_assets', sa.Column('commercial_use_approved', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('component_3d_assets', sa.Column('redistribution_approved', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('component_3d_assets', sa.Column('attribution', sa.String(length=500), nullable=True))
    op.add_column('component_3d_assets', sa.Column('provenance_reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('component_3d_assets', sa.Column('provenance_reviewed_by', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('component_3d_assets', 'provenance_reviewed_by')
    op.drop_column('component_3d_assets', 'provenance_reviewed_at')
    op.drop_column('component_3d_assets', 'attribution')
    op.drop_column('component_3d_assets', 'redistribution_approved')
    op.drop_column('component_3d_assets', 'commercial_use_approved')
    op.drop_column('component_3d_assets', 'licence_url')
    op.drop_column('component_3d_assets', 'licence')
    op.drop_column('component_3d_assets', 'source_url')
    op.drop_column('component_3d_assets', 'source_name')
    op.drop_column('component_3d_assets', 'provenance_status')
