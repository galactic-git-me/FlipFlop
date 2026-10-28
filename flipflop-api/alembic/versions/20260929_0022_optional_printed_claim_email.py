"""Allow email-free portal claims for printed indirect-channel leaflets.

Revision ID: 20260929_0022
Revises: 20260929_0021
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0022"
down_revision = "20260929_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "portal_access_grants",
        "contact_email",
        existing_type=sa.String(length=320),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        "UPDATE portal_access_grants SET contact_email = 'unavailable@invalid.example' "
        "WHERE contact_email IS NULL"
    )
    op.alter_column(
        "portal_access_grants",
        "contact_email",
        existing_type=sa.String(length=320),
        nullable=False,
    )
