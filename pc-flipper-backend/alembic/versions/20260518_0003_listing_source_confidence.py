"""add listing source confidence

Revision ID: 20260518_0003
Revises: 20260518_0002
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa

revision = "20260518_0003"
down_revision = "20260518_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("listings") as batch:
        batch.add_column(
            sa.Column(
                "source_confidence",
                sa.String(length=32),
                nullable=False,
                server_default="browser_verified",
            )
        )
    op.create_index("ix_listings_source_confidence", "listings", ["source_confidence"])


def downgrade() -> None:
    op.drop_index("ix_listings_source_confidence", table_name="listings")
    with op.batch_alter_table("listings") as batch:
        batch.drop_column("source_confidence")

