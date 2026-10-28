"""Persist customer portal claim email delivery state.

Revision ID: 20260929_0021
Revises: 20260929_0020
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0021"
down_revision = "20260929_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("portal_access_grants", sa.Column("email_status", sa.String(length=20), nullable=True))
    op.add_column("portal_access_grants", sa.Column("email_attempted_at", sa.DateTime(), nullable=True))
    op.add_column("portal_access_grants", sa.Column("email_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("portal_access_grants", "email_sent_at")
    op.drop_column("portal_access_grants", "email_attempted_at")
    op.drop_column("portal_access_grants", "email_status")
