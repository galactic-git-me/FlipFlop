"""Add single-use guest portal access grants.

Revision ID: 20260929_0003
Revises: 20260929_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0003"
down_revision = "20260929_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portal_access_grants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("manual_build_id", sa.Integer(), sa.ForeignKey("manual_builds.id"), nullable=True),
        sa.Column("contact_email", sa.String(length=320), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("channel", sa.String(length=60), nullable=False, server_default="direct_guest"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(length=320), nullable=True),
        sa.Column("leaflet_storage_key", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("(order_id IS NOT NULL AND manual_build_id IS NULL) OR (order_id IS NULL AND manual_build_id IS NOT NULL)", name="ck_portal_access_grant_one_source"),
    )
    op.create_index("ix_portal_access_grants_order_id", "portal_access_grants", ["order_id"])
    op.create_index("ix_portal_access_grants_manual_build_id", "portal_access_grants", ["manual_build_id"])
    op.create_index("ix_portal_access_grants_contact_email", "portal_access_grants", ["contact_email"])
    op.create_index("ix_portal_access_grants_token_hash", "portal_access_grants", ["token_hash"])
    op.create_index("ix_portal_access_grants_expires_at", "portal_access_grants", ["expires_at"])


def downgrade() -> None:
    op.drop_table("portal_access_grants")
