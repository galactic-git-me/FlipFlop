"""Add curated image and 3D model automation settings.

Revision ID: 20261112_0002
Revises: 20261105_0001
Create Date: 2026-11-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261112_0002"
down_revision: Union[str, None] = "20261105_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("auto_approve_images", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "app_settings",
        sa.Column("auto_generate_3d_models", sa.Boolean(), server_default=sa.true(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "auto_generate_3d_models")
    op.drop_column("app_settings", "auto_approve_images")
