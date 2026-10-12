"""Persist structured customer-facing catalogue copy.

Revision ID: 20261012_0002
Revises: 20261012_0001
Create Date: 2026-10-12
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261012_0002"
down_revision: Union[str, None] = "20261012_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("catalogue_marketing_copy"):
        # Local startup create_all may create newly registered model tables
        # before Alembic records the corresponding revision. Adopt only the
        # complete expected schema; never silently accept a partial table.
        columns = {column["name"] for column in inspector.get_columns("catalogue_marketing_copy")}
        required = {
            "id", "subject_type", "subject_id", "context_key", "copy", "source_hash",
            "provider", "model", "prompt_tokens", "completion_tokens", "generated_at", "updated_at", "last_error",
        }
        unique_constraints = {
            constraint.get("name") for constraint in inspector.get_unique_constraints("catalogue_marketing_copy")
        }
        if not required.issubset(columns) or "uq_catalogue_marketing_copy_subject_context" not in unique_constraints:
            raise RuntimeError("Existing catalogue_marketing_copy table does not match the expected schema")
        return

    op.create_table(
        "catalogue_marketing_copy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subject_type", sa.String(length=30), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=False),
        sa.Column("context_key", sa.String(length=255), nullable=False, server_default="product"),
        sa.Column("copy", sa.JSON(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint("subject_type", "subject_id", "context_key", name="uq_catalogue_marketing_copy_subject_context"),
    )
    op.create_index("ix_catalogue_marketing_copy_subject_type", "catalogue_marketing_copy", ["subject_type"])
    op.create_index("ix_catalogue_marketing_copy_subject_id", "catalogue_marketing_copy", ["subject_id"])


def downgrade() -> None:
    op.drop_index("ix_catalogue_marketing_copy_subject_id", table_name="catalogue_marketing_copy")
    op.drop_index("ix_catalogue_marketing_copy_subject_type", table_name="catalogue_marketing_copy")
    op.drop_table("catalogue_marketing_copy")
