"""Store private customer support case evidence metadata.

Revision ID: 20260929_0012
Revises: 20260929_0011
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0012"
down_revision = "20260929_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("customer_problems", sa.Column("evidence_files", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("customer_problems", "evidence_files")
