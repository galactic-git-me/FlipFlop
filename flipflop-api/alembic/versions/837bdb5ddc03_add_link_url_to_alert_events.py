"""add link_url to alert_events

Revision ID: 837bdb5ddc03
Revises: 1f83fbbf32fa
Create Date: 2026-08-10 00:08:42.410388

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '837bdb5ddc03'
down_revision: Union[str, None] = '1f83fbbf32fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "alert_events",
        sa.Column("link_url", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("alert_events", "link_url")
