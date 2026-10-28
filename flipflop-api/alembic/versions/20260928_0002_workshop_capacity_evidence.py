"""Persist timestamped, sourced workshop capacity observations."""
from alembic import op
import sqlalchemy as sa

revision = "vnext_20260928_02"
down_revision = "vnext_20260928_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workshop_capacity_evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("build_week", sa.String(length=8), nullable=False),
        sa.Column("available_builds", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_source", sa.String(length=160), nullable=False),
        sa.Column("evidence_ref", sa.String(length=500), nullable=False),
        sa.Column("captured_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workshop_capacity_evidence_build_week",
        "workshop_capacity_evidence",
        ["build_week"],
    )


def downgrade() -> None:
    op.drop_index("ix_workshop_capacity_evidence_build_week", table_name="workshop_capacity_evidence")
    op.drop_table("workshop_capacity_evidence")
