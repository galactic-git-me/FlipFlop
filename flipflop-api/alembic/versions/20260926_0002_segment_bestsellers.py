"""Store reviewed bestseller references on draft build segments."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cb_20260926_02_refs"
down_revision: Union[str, None] = "cb_20260926_01_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("curated_build_segments", sa.Column("bestseller_components", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("curated_build_segments", "bestseller_components")
