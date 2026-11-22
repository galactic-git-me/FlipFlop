"""Persist post-scrape GEM build QA snapshots.

Revision ID: 20261122_0001
Revises: 20261116_0002
Create Date: 2026-11-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261122_0001"
down_revision: Union[str, None] = "20261116_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "gem_radar_build_qa_events"
    if inspector.has_table(table_name):
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        unique_constraints = {
            constraint.get("name") for constraint in inspector.get_unique_constraints(table_name)
        }
        indexes = {index.get("name") for index in inspector.get_indexes(table_name)}
        required_columns = {
            "id", "environment", "sweep_run_id", "completed_at", "status", "attempts",
            "processing_started_at", "payload", "sheet_sync_status", "sheet_sync_error", "created_at",
        }
        if (not required_columns.issubset(columns)
                or "uq_gem_build_qa_environment_run" not in unique_constraints
                or "ix_gem_radar_build_qa_events_environment" not in indexes):
            raise RuntimeError(f"Existing {table_name} table does not match the expected schema")
        return

    op.create_table(
        table_name,
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("environment", sa.String(length=8), nullable=False),
        sa.Column("sweep_run_id", sa.String(length=64), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("sheet_sync_status", sa.String(length=32), nullable=False, server_default="not_configured"),
        sa.Column("sheet_sync_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("environment", "sweep_run_id", name="uq_gem_build_qa_environment_run"),
    )
    op.create_index("ix_gem_radar_build_qa_events_environment", table_name, ["environment"])


def downgrade() -> None:
    op.drop_index("ix_gem_radar_build_qa_events_environment", table_name="gem_radar_build_qa_events")
    op.drop_table("gem_radar_build_qa_events")
