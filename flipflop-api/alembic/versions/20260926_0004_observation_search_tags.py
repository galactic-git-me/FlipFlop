"""Keep search tags with listing observations for scored result display."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cb_20260926_04_obs_tags"
down_revision: Union[str, None] = "cb_20260926_03_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "gem_radar_listing_observations",
        sa.Column("search_tags", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("gem_radar_listing_observations", "search_tags")
