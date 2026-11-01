"""Merge browser listings and newsletter schema heads."""

from typing import Sequence, Union


revision: str = "20261031_0002"
down_revision: Union[str, tuple[str, str, str], None] = (
    "20261030_0001",
    "20261030_dev_browser",
    "20261031_0001",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
