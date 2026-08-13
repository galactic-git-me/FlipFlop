"""Merge eBay migrations

Revision ID: 20260806_0003
Revises: 20260806_0001, 20260806_0002
Create Date: 2026-08-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20260806_0003'
down_revision: Union[str, Sequence[str], None] = ('20260806_0001', '20260806_0002')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
