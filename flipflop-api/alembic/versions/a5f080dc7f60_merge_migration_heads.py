"""Merge migration heads

Revision ID: a5f080dc7f60
Revises: 20260727_0023, 20260801_0007
Create Date: 2026-08-01 16:46:58.416916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5f080dc7f60'
down_revision: Union[str, None] = ('20260727_0023', '20260801_0007')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
