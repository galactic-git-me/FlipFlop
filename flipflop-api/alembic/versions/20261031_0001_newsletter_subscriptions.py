"""Add double opt-in newsletter subscriptions.

Revision ID: 20261031_0001
Revises: 20261012_merge_heads
Create Date: 2026-10-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261031_0001"
down_revision: Union[str, None] = "20261012_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "newsletter_subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consent_version", sa.String(length=40), server_default="footer-v1", nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmation_token_hash", sa.String(length=64), nullable=True),
        sa.Column("confirmation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("unsubscribe_token_hash", sa.String(length=64), nullable=True),
        sa.Column("unsubscribed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_newsletter_subscriptions_email"),
        sa.UniqueConstraint("confirmation_token_hash"),
        sa.UniqueConstraint("unsubscribe_token_hash"),
    )
    op.create_index("ix_newsletter_subscriptions_customer_id", "newsletter_subscriptions", ["customer_id"])
    op.create_index("ix_newsletter_subscriptions_status", "newsletter_subscriptions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_newsletter_subscriptions_status", table_name="newsletter_subscriptions")
    op.drop_index("ix_newsletter_subscriptions_customer_id", table_name="newsletter_subscriptions")
    op.drop_table("newsletter_subscriptions")
