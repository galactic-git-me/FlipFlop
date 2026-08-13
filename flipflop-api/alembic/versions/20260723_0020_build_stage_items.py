"""Build fulfillment checklists — per-build task tracking during BUILD stage.

Separate from OrderChecklist to avoid contaminating CXP order pipeline.
Tracks admin tasks: software, 3D model, pictures, performance tests, registration plate.

Revision ID: 20260723_0020
Revises: 20260723_0019
Create Date: 2026-07-23
"""
from alembic import op
import sqlalchemy as sa

revision = "20260723_0020"
down_revision = "20260723_0019"
depends_on = None


def upgrade():
    op.create_table(
        "build_stage_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("build_id", sa.Integer(), sa.ForeignKey("builds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("section", sa.String(50), nullable=False),
        sa.Column("item", sa.String(255), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("file_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_build_stage_items_build_id", "build_stage_items", ["build_id"])
    op.create_index("ix_build_stage_items_section", "build_stage_items", ["section"])
    op.create_index("ix_build_stage_items_completed", "build_stage_items", ["completed"])


def downgrade():
    op.drop_index("ix_build_stage_items_completed", table_name="build_stage_items")
    op.drop_index("ix_build_stage_items_section", table_name="build_stage_items")
    op.drop_index("ix_build_stage_items_build_id", table_name="build_stage_items")
    op.drop_table("build_stage_items")
