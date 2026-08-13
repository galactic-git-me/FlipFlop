"""add dimension/clearance/style columns to case_catalogue

Revision ID: c8b4e1a9d3f2
Revises: f3a1c9d2e7b4
Create Date: 2026-08-12 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8b4e1a9d3f2'
down_revision: Union[str, None] = 'f3a1c9d2e7b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('case_catalogue', sa.Column('height_mm', sa.Float(), nullable=True))
    op.add_column('case_catalogue', sa.Column('width_mm', sa.Float(), nullable=True))
    op.add_column('case_catalogue', sa.Column('depth_mm', sa.Float(), nullable=True))
    op.add_column('case_catalogue', sa.Column('max_gpu_length_mm', sa.Float(), nullable=True))
    op.add_column('case_catalogue', sa.Column('max_cooler_height_mm', sa.Float(), nullable=True))
    op.add_column('case_catalogue', sa.Column('radiator_support', sa.JSON(), nullable=True))
    op.add_column('case_catalogue', sa.Column('style_tags', sa.JSON(), nullable=True))
    op.add_column('case_catalogue', sa.Column('colour', sa.String(length=50), nullable=True))
    op.add_column('case_catalogue', sa.Column('rgb_zones', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('case_catalogue', 'rgb_zones')
    op.drop_column('case_catalogue', 'colour')
    op.drop_column('case_catalogue', 'style_tags')
    op.drop_column('case_catalogue', 'radiator_support')
    op.drop_column('case_catalogue', 'max_cooler_height_mm')
    op.drop_column('case_catalogue', 'max_gpu_length_mm')
    op.drop_column('case_catalogue', 'depth_mm')
    op.drop_column('case_catalogue', 'width_mm')
    op.drop_column('case_catalogue', 'height_mm')
