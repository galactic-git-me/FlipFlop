"""Add missing model columns without deleting legacy data.

Revision ID: 20261009_0001
Revises: 20260930_0017
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261009_0001"
down_revision: Union[str, None] = "20260930_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column(table: str, column: sa.Column) -> bool:
    """Add one column only when the existing dev schema lacks it."""
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        raise RuntimeError(f"Cannot repair {table}.{column.name}: table is missing")
    if column.name in {item["name"] for item in inspector.get_columns(table)}:
        return False
    op.add_column(table, column)
    return True


def _add_required(table: str, name: str, type_: sa.types.TypeEngine, default: str) -> None:
    if _add_column(table, sa.Column(name, type_, nullable=False, server_default=sa.text(default))):
        # The default only backfills existing rows. Keep the ORM's normal
        # insert behavior as the source of defaults for future writes.
        op.alter_column(table, name, server_default=None)


def upgrade() -> None:
    # Preserve the cancellation enum addition from the skipped historical
    # migrations. PostgreSQL safely ignores this when the label already exists.
    if op.get_context().dialect.name == "postgresql":
        op.execute("ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'CANCELLED'")

    _add_required("app_settings", "ai_setup_offers", sa.JSON(), "'[]'::json")
    _add_required("app_settings", "flexible_curated_custom_days", sa.Integer(), "10")

    _add_column("curated_build_segments", sa.Column("software_profile", sa.JSON(), nullable=True))
    _add_required("curated_build_segments", "approved_upgrades", sa.JSON(), "'[]'::json")
    _add_required("curated_build_segments", "allow_flip_component_sources", sa.Boolean(), "false")

    for table in ("gem_radar_listing_observations", "gem_radar_scored_listings"):
        _add_column(table, sa.Column("prime_eligible", sa.Boolean(), nullable=True))
        _add_column(table, sa.Column("delivery_working_days", sa.Integer(), nullable=True))
        _add_column(table, sa.Column("delivery_estimate_source", sa.String(length=32), nullable=True))

    _add_column("manual_builds", sa.Column("shipping_insurance_policy_id", sa.String(length=120), nullable=True))
    _add_column("manual_builds", sa.Column("shipping_insurance_invoice_id", sa.String(length=120), nullable=True))
    _add_column("manual_builds", sa.Column("shipping_insurance_cost_gbp", sa.Float(), nullable=True))
    _add_required("manual_builds", "shipping_insurance_status", sa.String(length=40), "'not_created'")
    _add_column("manual_builds", sa.Column("shipping_insurance_created_at", sa.DateTime(), nullable=True))
    _add_column("manual_builds", sa.Column("parcel2go_order_line_id", sa.String(length=100), nullable=True))
    state_added = _add_required("manual_builds", "shipment_booking_state", sa.String(length=40), "'not_started'")
    _add_column("manual_builds", sa.Column("shipment_booking_attempted_at", sa.DateTime(), nullable=True))
    _add_column("manual_builds", sa.Column("shipment_booking_error_code", sa.String(length=80), nullable=True))
    if state_added:
        op.execute(
            "UPDATE manual_builds SET shipment_booking_state = 'booked' "
            "WHERE parcel2go_order_id IS NOT NULL OR shipment_booked_at IS NOT NULL"
        )

    for name, type_ in (
        ("cancellation_requested_at", sa.DateTime()),
        ("cancellation_status", sa.String(length=32)),
        ("refund_id", sa.String(length=100)),
        ("cancelled_at", sa.DateTime()),
        ("change_request", sa.JSON()),
    ):
        _add_column("orders", sa.Column(name, type_, nullable=True))

    for name, type_, nullable, default in (
        ("rrp", sa.Float(), True, None),
        ("form_factors", sa.JSON(), True, None),
        ("keywords", sa.JSON(), True, None),
        ("selection_count", sa.Integer(), False, "0"),
        ("rating", sa.Float(), True, None),
        ("review_count", sa.Integer(), True, None),
        ("sales_velocity", sa.String(length=100), True, None),
        ("bestseller_rank", sa.Integer(), True, None),
        ("has_3d_model", sa.Boolean(), False, "false"),
    ):
        if nullable:
            _add_column("parts", sa.Column(name, type_, nullable=True))
        else:
            _add_required("parts", name, type_, default)

    _add_column("products", sa.Column("checkout_addresses", sa.JSON(), nullable=True))
    _add_column("playbooks", sa.Column("software_profile", sa.JSON(), nullable=True))

    for name, type_ in (
        ("manual_build_id", sa.Integer()),
        ("portal_grant_id", sa.Integer()),
        ("evidence_files", sa.JSON()),
        ("repair_tracking", sa.JSON()),
        ("repair_tracking_audit", sa.JSON()),
        ("repair_tracking_provider", sa.String(length=40)),
        ("repair_tracking_provider_reference", sa.String(length=120)),
    ):
        _add_column("customer_problems", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    raise RuntimeError(
        "This additive repair may contain newly written data. Restore a verified "
        "database backup instead of dropping repaired columns."
    )
