"""add family_key to component_3d_assets for bucket-level generics

Revision ID: e4f7a1c9b3d6
Revises: d1e5f7a2b8c3
Create Date: 2026-08-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4f7a1c9b3d6'
down_revision: Union[str, None] = 'd1e5f7a2b8c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('component_3d_assets', sa.Column('family_key', sa.String(length=60), nullable=True))
    op.create_index(
        'ix_c3da_category_family',
        'component_3d_assets',
        ['category', 'family_key', 'is_active'],
    )


def downgrade() -> None:
    op.drop_index('ix_c3da_category_family', table_name='component_3d_assets')
    op.drop_column('component_3d_assets', 'family_key')
