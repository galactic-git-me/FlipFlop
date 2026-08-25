"""Stop treating unknown historic sold-build conditions as used.

Revision ID: 20260825_0012
Revises: 20260825_0011
"""
from alembic import op
import sqlalchemy as sa

revision = "20260825_0012"
down_revision = "20260825_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("build_sold_observations", "condition", server_default="unknown")
    op.execute(sa.text("""
        UPDATE build_sold_observations
        SET condition = 'unknown'
        WHERE condition = 'used' AND match_basis LIKE 'Extension sold search:%'
    """))


def downgrade() -> None:
    op.alter_column("build_sold_observations", "condition", server_default="used")
