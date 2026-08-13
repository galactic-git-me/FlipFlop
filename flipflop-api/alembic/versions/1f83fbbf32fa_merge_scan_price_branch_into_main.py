"""merge scan_price branch into main

Revision ID: 1f83fbbf32fa
Revises: 097b6aff6ac2, 20260809_0005
Create Date: 2026-08-10 00:04:25.207739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1f83fbbf32fa'
down_revision: Union[str, None] = ('097b6aff6ac2', '20260809_0005')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
