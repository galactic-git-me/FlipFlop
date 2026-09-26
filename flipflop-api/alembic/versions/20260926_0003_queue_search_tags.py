"""Persist extension search tags on queued submissions."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cb_20260926_03_tags"
down_revision: Union[str, None] = "cb_20260926_02_refs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "submission_queue",
        sa.Column("search_tags", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("submission_queue", "search_tags")
