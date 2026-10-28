"""Keep inbound and outbound warranty parcels as separate shipment legs.

Revision ID: 20260929_0020
Revises: 20260929_0019
"""
from alembic import op
import sqlalchemy as sa


revision = "20260929_0020"
down_revision = "20260929_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_problem_shipments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("customer_problem_id", sa.Integer(), sa.ForeignKey("customer_problems.id", ondelete="CASCADE"), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("carrier", sa.String(length=100), nullable=False),
        sa.Column("tracking_number", sa.String(length=160), nullable=False),
        sa.Column("tracking_url", sa.String(length=500), nullable=False),
        sa.Column("provider", sa.String(length=40), nullable=True),
        sa.Column("provider_reference", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("purpose IN ('customer_return', 'replacement')", name="ck_customer_problem_shipment_purpose"),
        sa.CheckConstraint(
            "(provider IS NULL AND provider_reference IS NULL) OR "
            "(provider = 'parcel2go' AND provider_reference IS NOT NULL)",
            name="ck_customer_problem_shipment_provider_reference",
        ),
        sa.UniqueConstraint("customer_problem_id", "purpose", name="uq_customer_problem_shipment_purpose"),
        sa.UniqueConstraint("provider", "provider_reference", name="uq_customer_problem_shipment_provider_reference"),
    )
    op.create_index("ix_customer_problem_shipments_customer_problem_id", "customer_problem_shipments", ["customer_problem_id"])

    with op.batch_alter_table("shipment_tracking_events") as batch:
        batch.add_column(sa.Column("customer_problem_shipment_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_shipment_event_customer_problem_shipment",
            "customer_problem_shipments",
            ["customer_problem_shipment_id"],
            ["id"],
        )
        batch.drop_constraint("ck_shipment_event_one_source", type_="check")
        batch.create_check_constraint(
            "ck_shipment_event_one_source",
            "(order_id IS NOT NULL AND manual_build_id IS NULL AND customer_problem_id IS NULL AND customer_problem_shipment_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL AND customer_problem_id IS NULL AND customer_problem_shipment_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NULL AND customer_problem_id IS NOT NULL AND customer_problem_shipment_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NULL AND customer_problem_id IS NULL AND customer_problem_shipment_id IS NOT NULL)",
        )
        batch.create_index("ix_shipment_tracking_events_customer_problem_shipment_id", ["customer_problem_shipment_id"])

    bind = op.get_bind()
    problems = sa.Table("customer_problems", sa.MetaData(), autoload_with=bind)
    events = sa.Table("shipment_tracking_events", sa.MetaData(), autoload_with=bind)
    shipments = sa.Table("customer_problem_shipments", sa.MetaData(), autoload_with=bind)
    for problem in bind.execute(sa.select(problems)).mappings():
        raw_tracking = problem["repair_tracking"]
        tracking = raw_tracking if isinstance(raw_tracking, dict) else {}
        case_events = list(bind.execute(sa.select(events).where(events.c.customer_problem_id == problem["id"])).mappings())
        if not tracking and not problem["repair_tracking_provider_reference"] and not case_events:
            continue
        purpose = tracking.get("purpose")
        if purpose not in {"customer_return", "replacement"}:
            purpose = "customer_return"
        bind.execute(
            sa.insert(shipments).values(
                customer_problem_id=problem["id"],
                purpose=purpose,
                carrier=tracking.get("carrier") or "Parcel2Go",
                tracking_number=tracking.get("tracking_number") or "legacy-reference",
                tracking_url=tracking.get("tracking_url") or "https://www.parcel2go.com/",
                provider=problem["repair_tracking_provider"],
                provider_reference=problem["repair_tracking_provider_reference"],
                created_at=problem["created_at"],
                updated_at=problem["updated_at"],
            )
        )
        shipment_id = bind.execute(
            sa.select(shipments.c.id).where(
                shipments.c.customer_problem_id == problem["id"],
                shipments.c.purpose == purpose,
            )
        ).scalar_one()
        if case_events:
            bind.execute(
                sa.update(events)
                .where(events.c.customer_problem_id == problem["id"])
                .values(customer_problem_id=None, customer_problem_shipment_id=shipment_id)
            )
        if problem["repair_tracking_provider_reference"]:
            bind.execute(
                sa.update(problems)
                .where(problems.c.id == problem["id"])
                .values(repair_tracking_provider=None, repair_tracking_provider_reference=None)
            )


def downgrade() -> None:
    bind = op.get_bind()
    problems = sa.Table("customer_problems", sa.MetaData(), autoload_with=bind)
    events = sa.Table("shipment_tracking_events", sa.MetaData(), autoload_with=bind)
    shipments = sa.Table("customer_problem_shipments", sa.MetaData(), autoload_with=bind)
    shipment_rows = list(bind.execute(sa.select(shipments)).mappings())
    if any(row["purpose"] != "customer_return" for row in shipment_rows):
        raise RuntimeError("Cannot downgrade while outbound repair shipment legs exist")
    for shipment in shipment_rows:
        bind.execute(
            sa.update(events)
            .where(events.c.customer_problem_shipment_id == shipment["id"])
            .values(customer_problem_id=shipment["customer_problem_id"], customer_problem_shipment_id=None)
        )
        if shipment["provider_reference"]:
            bind.execute(
                sa.update(problems)
                .where(problems.c.id == shipment["customer_problem_id"])
                .values(
                    repair_tracking_provider=shipment["provider"],
                    repair_tracking_provider_reference=shipment["provider_reference"],
                )
            )
    with op.batch_alter_table("shipment_tracking_events") as batch:
        batch.drop_index("ix_shipment_tracking_events_customer_problem_shipment_id")
        batch.drop_constraint("ck_shipment_event_one_source", type_="check")
        batch.create_check_constraint(
            "ck_shipment_event_one_source",
            "(order_id IS NOT NULL AND manual_build_id IS NULL AND customer_problem_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NOT NULL AND customer_problem_id IS NULL) OR "
            "(order_id IS NULL AND manual_build_id IS NULL AND customer_problem_id IS NOT NULL)",
        )
        batch.drop_constraint("fk_shipment_event_customer_problem_shipment", type_="foreignkey")
        batch.drop_column("customer_problem_shipment_id")
    op.drop_index("ix_customer_problem_shipments_customer_problem_id", table_name="customer_problem_shipments")
    op.drop_table("customer_problem_shipments")
