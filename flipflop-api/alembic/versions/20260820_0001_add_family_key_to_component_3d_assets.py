"""Add family_key column to component_3d_assets for bucket-level generics

Revision ID: 20260820_0001
Revises: 20260819_0004
Create Date: 2026-08-20

The family_key column stores the bucket within a category (e.g., "gpu_large_triple_fan",
"mobo_asus_atx"). This enables "model each family once, cache forever" strategy where
one generic recreation is reused across every catalogue variant that classifies into it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '20260820_0001'
down_revision: Union[str, None] = '20260819_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Some early deployments created this model column through metadata
    # bootstrap before the Alembic revision was applied. Treat that state as
    # already migrated so the remaining revision chain can run normally.
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('component_3d_assets')}
    if 'family_key' not in columns:
        op.add_column('component_3d_assets', sa.Column('family_key', sa.String(length=60), nullable=True))


def downgrade() -> None:
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('component_3d_assets')}
    if 'family_key' in columns:
        op.drop_column('component_3d_assets', 'family_key')
