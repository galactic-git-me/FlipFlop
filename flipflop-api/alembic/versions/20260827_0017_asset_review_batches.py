"""Add owner-controlled batches for 3D asset review.

Revision ID: 20260827_0017
Revises: 20260826_0016
"""
from alembic import op
import sqlalchemy as sa

revision = "20260827_0017"
down_revision = "20260826_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("component_3d_assets", sa.Column("review_batch_id", sa.String(36), nullable=True))
    op.add_column("component_3d_assets", sa.Column("review_decision", sa.String(20), nullable=True))
    op.add_column("component_3d_assets", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("component_3d_assets", sa.Column("reviewed_by", sa.String(100), nullable=True))
    op.create_index("ix_component_3d_assets_review_batch_id", "component_3d_assets", ["review_batch_id"])
    op.add_column("cases", sa.Column("priority_3d_rank", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("priority_3d_batch", sa.Integer(), nullable=True))
    op.add_column("cases", sa.Column("priority_3d_frozen_at", sa.DateTime(), nullable=True))
    op.add_column("cases", sa.Column("sourcing_3d_evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'")))
    op.create_index("ix_cases_priority_3d_rank", "cases", ["priority_3d_rank"])
    op.create_index("ix_cases_priority_3d_batch", "cases", ["priority_3d_batch"])


def downgrade() -> None:
    op.drop_index("ix_cases_priority_3d_batch", table_name="cases")
    op.drop_index("ix_cases_priority_3d_rank", table_name="cases")
    op.drop_column("cases", "sourcing_3d_evidence")
    op.drop_column("cases", "priority_3d_frozen_at")
    op.drop_column("cases", "priority_3d_batch")
    op.drop_column("cases", "priority_3d_rank")
    op.drop_index("ix_component_3d_assets_review_batch_id", table_name="component_3d_assets")
    op.drop_column("component_3d_assets", "reviewed_by")
    op.drop_column("component_3d_assets", "reviewed_at")
    op.drop_column("component_3d_assets", "review_decision")
    op.drop_column("component_3d_assets", "review_batch_id")
