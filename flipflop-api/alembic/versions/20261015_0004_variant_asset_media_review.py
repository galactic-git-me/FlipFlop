"""persist catalogue variant photo and video approval

Revision ID: 20261015_0004
Revises: 20261015_0003
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261015_0004"
down_revision: Union[str, None] = "20261015_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("catalogue_variants", sa.Column("asset_media_review", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("catalogue_variants", "asset_media_review")
