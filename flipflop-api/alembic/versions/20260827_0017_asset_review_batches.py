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


def downgrade() -> None:
    op.drop_index("ix_component_3d_assets_review_batch_id", table_name="component_3d_assets")
    op.drop_column("component_3d_assets", "reviewed_by")
    op.drop_column("component_3d_assets", "reviewed_at")
    op.drop_column("component_3d_assets", "review_decision")
    op.drop_column("component_3d_assets", "review_batch_id")
