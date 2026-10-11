"""Add the admin-curated component manual cache.

Revision ID: 20260929_0008
Revises: 20260929_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0008"
down_revision = "20260929_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "component_manuals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("component_key", sa.String(length=240), nullable=False),
        sa.Column("component_name", sa.String(length=300), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("storage_key", sa.String(length=500), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("component_key", name="uq_component_manuals_component_key"),
    )


def downgrade() -> None:
    op.drop_table("component_manuals")
