"""add cpk to gem_radar_favourites

Revision ID: 3348793fd2db
Revises: 837bdb5ddc03
Create Date: 2026-08-10 00:13:20.630614

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3348793fd2db'
down_revision: Union[str, None] = '837bdb5ddc03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gem_radar_favourites",
        sa.Column("cpk", sa.String(length=400), nullable=True),
    )
    op.create_index(
        "ix_gem_radar_favourites_cpk", "gem_radar_favourites", ["cpk"]
    )


def downgrade() -> None:
    op.drop_index("ix_gem_radar_favourites_cpk", table_name="gem_radar_favourites")
    op.drop_column("gem_radar_favourites", "cpk")
