"""Draft builds — saved, unfinished playbook configurations customers can
resume later. config_json mirrors PlaybookBuildConfig and is re-priced live
from the catalogue on read, not stored as a stale total.

Revision ID: 20260717_0018
Revises: 20260717_0017
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = "20260717_0018"
down_revision = "20260717_0017"
depends_on = None


def upgrade():
    op.create_table(
        "draft_builds",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("playbook_id", sa.Integer(), sa.ForeignKey("playbooks.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_draft_builds_customer_id", "draft_builds", ["customer_id"])


def downgrade():
    op.drop_index("ix_draft_builds_customer_id", table_name="draft_builds")
    op.drop_table("draft_builds")
