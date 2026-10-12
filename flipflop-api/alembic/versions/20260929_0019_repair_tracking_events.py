"""Attach courier events to warranty repair shipments.

Revision ID: 20260929_0019
Revises: 20260929_0018
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0019"
down_revision = "20260929_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("customer_problems") as batch:
        batch.add_column(sa.Column("repair_tracking_provider", sa.String(length=40), nullable=True))
        batch.add_column(sa.Column("repair_tracking_provider_reference", sa.String(length=120), nullable=True))
        batch.create_unique_constraint(
            "uq_customer_problem_repair_provider_reference",
            ["repair_tracking_provider_reference"],
        )
        batch.create_check_constraint(
            "ck_customer_problem_repair_tracking_provider_reference",
            "(repair_tracking_provider IS NULL AND repair_tracking_provider_reference IS NULL) OR "
            "(repair_tracking_provider = 'parcel2go' AND repair_tracking_provider_reference IS NOT NULL)",
        )

    with op.batch_alter_table("shipment_tracking_events") as batch:
        batch.add_column(sa.Column("customer_problem_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_shipment_event_customer_problem",
            "customer_problems",
            ["customer_problem_id"],
            ["id"],
        )
        batch.drop_constraint("ck_shipment_event_one_source", type_="check")
        batch.create_check_constraint(
            "ck_shipment_event_one_source",
            "(order_id IS NOT NULL AND manual_build_id IS NULL AND customer_problem_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL AND customer_problem_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NULL AND customer_problem_id IS NOT NULL)",
        )
        batch.create_index("ix_shipment_tracking_events_customer_problem_id", ["customer_problem_id"])


def downgrade() -> None:
    bind = op.get_bind()
    has_repair_references = bind.execute(
        sa.text("SELECT 1 FROM customer_problems WHERE repair_tracking_provider_reference IS NOT NULL LIMIT 1")
    ).first()
    has_repair_events = bind.execute(
        sa.text("SELECT 1 FROM shipment_tracking_events WHERE customer_problem_id IS NOT NULL LIMIT 1")
    ).first()
    if has_repair_references or has_repair_events:
        raise RuntimeError("Cannot downgrade while repair shipment tracking references or events exist")

    with op.batch_alter_table("shipment_tracking_events") as batch:
        batch.drop_index("ix_shipment_tracking_events_customer_problem_id")
        batch.drop_constraint("ck_shipment_event_one_source", type_="check")
        batch.create_check_constraint(
            "ck_shipment_event_one_source",
            "(order_id IS NOT NULL AND manual_build_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL)",
        )
        batch.drop_constraint("fk_shipment_event_customer_problem", type_="foreignkey")
        batch.drop_column("customer_problem_id")

    with op.batch_alter_table("customer_problems") as batch:
        batch.drop_constraint("ck_customer_problem_repair_tracking_provider_reference", type_="check")
        batch.drop_constraint("uq_customer_problem_repair_provider_reference", type_="unique")
        batch.drop_column("repair_tracking_provider_reference")
        batch.drop_column("repair_tracking_provider")
