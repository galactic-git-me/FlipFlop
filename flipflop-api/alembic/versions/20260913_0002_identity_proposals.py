"""add reviewable sold-observation identity proposals

Revision ID: 20260913_0002
Revises: 20260913_0001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260913_0002"
down_revision: Union[str, None] = "20260913_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "gem_radar_identity_proposals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sold_observation_id", sa.Integer(), nullable=False),
        sa.Column("suggested_cpk", sa.String(length=64), nullable=True),
        sa.Column("candidate_cpks", sa.JSON(), nullable=True),
        sa.Column("method", sa.String(length=40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("reviewer", sa.String(length=100), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("sold_observation_id", name="uq_identity_proposal_sold_observation"),
    )
    op.create_index("ix_gem_radar_identity_proposals_status", "gem_radar_identity_proposals", ["status"])
    op.create_index("ix_gem_radar_identity_proposals_candidate", "gem_radar_identity_proposals", ["suggested_cpk"])


def downgrade() -> None:
    op.drop_index("ix_gem_radar_identity_proposals_candidate", table_name="gem_radar_identity_proposals")
    op.drop_index("ix_gem_radar_identity_proposals_status", table_name="gem_radar_identity_proposals")
    op.drop_table("gem_radar_identity_proposals")
