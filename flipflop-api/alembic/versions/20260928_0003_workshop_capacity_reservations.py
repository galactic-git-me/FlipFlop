"""Add short-lived workshop capacity holds and append-only events."""
from alembic import op
import sqlalchemy as sa

revision = "vnext_20260928_03"
down_revision = "vnext_20260928_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workshop_capacity_reservations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("quote_snapshot_id", sa.Integer(), sa.ForeignKey("price_quote_snapshots.id"), nullable=False),
        sa.Column("capacity_evidence_id", sa.Integer(), sa.ForeignKey("workshop_capacity_evidence.id"), nullable=False),
        sa.Column("build_week", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("quote_snapshot_id", name="uq_capacity_reservation_quote"),
    )
    op.create_index("ix_workshop_capacity_reservations_build_week", "workshop_capacity_reservations", ["build_week"])
    op.create_table(
        "workshop_capacity_reservation_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("workshop_capacity_reservations.id"), nullable=False),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=True),
        sa.Column("admin_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workshop_capacity_reservation_events")
    op.drop_index("ix_workshop_capacity_reservations_build_week", table_name="workshop_capacity_reservations")
    op.drop_table("workshop_capacity_reservations")
