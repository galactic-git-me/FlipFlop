"""Scope courier event deduplication IDs to their provider.

Revision ID: 20260929_0005
Revises: 20260929_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20260929_0005"
down_revision = "20260929_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Carrier event IDs are only unique within a provider. Batch mode keeps
    # this migration usable with SQLite development databases as well as the
    # production PostgreSQL schema.
    naming_convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    inspector = sa.inspect(op.get_bind())
    unique_constraints = inspector.get_unique_constraints("shipment_tracking_events")
    with op.batch_alter_table(
        "shipment_tracking_events",
        naming_convention=naming_convention,
    ) as batch_op:
        for constraint in unique_constraints:
            if constraint.get("column_names") == ["provider_event_id"]:
                constraint_name = constraint.get("name") or "uq_shipment_tracking_events_provider_event_id"
                batch_op.drop_constraint(constraint_name, type_="unique")
        batch_op.create_unique_constraint(
            "uq_shipment_event_provider_event_id",
            ["provider", "provider_event_id"],
        )


def downgrade() -> None:
    naming_convention = {"uq": "uq_%(table_name)s_%(column_0_name)s"}
    with op.batch_alter_table(
        "shipment_tracking_events",
        naming_convention=naming_convention,
    ) as batch_op:
        batch_op.drop_constraint("uq_shipment_event_provider_event_id", type_="unique")
        batch_op.create_unique_constraint(
            "uq_shipment_tracking_events_provider_event_id",
            ["provider_event_id"],
        )
