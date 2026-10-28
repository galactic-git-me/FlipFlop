"""Persist admin decisions on Amazon bestseller marketplace matches."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cb_20260926_01_review"
down_revision: Union[str, tuple[str, str]] = ("cb_20260925_02_custom", "cb_20260925_03_delivery")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "curated_bestseller_reviews",
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("cpk", sa.String(255), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_by", sa.String(100), nullable=True),
        sa.PrimaryKeyConstraint("category", "cpk"),
        sa.CheckConstraint("status IN ('approved', 'rejected')", name="ck_bestseller_review_status"),
    )


def downgrade() -> None:
    op.drop_table("curated_bestseller_reviews")
