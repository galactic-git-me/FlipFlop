"""add editable RGB fan layouts to 3D assets

Revision ID: 20261012_0001
Revises: 20261009_0001
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261012_0001"
down_revision: Union[str, None] = "20261009_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("component_3d_assets", sa.Column("fan_layout_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("component_3d_assets", "fan_layout_json")
