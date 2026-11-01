"""Separate payment state from order fulfilment state.

Revision ID: 20261019_0001
Revises: 20261015_0004
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261019_0001"
down_revision: Union[str, None] = "20261015_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(name: str, column: sa.Column) -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("orders"):
        raise RuntimeError("Cannot add order payment state: orders table is missing")
    if name not in {item["name"] for item in inspector.get_columns("orders")}:
        op.add_column("orders", column)


def _create_index_if_missing(name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    if name not in {item["name"] for item in inspector.get_indexes("orders")}:
        op.create_index(name, "orders", columns)


def upgrade() -> None:
    # Orders are created after Stripe confirms payment. Existing cancelled
    # orders with a completed refund are the only records known to be refunded.
    _add_column_if_missing(
        "payment_status",
        sa.Column("payment_status", sa.String(length=32), nullable=False, server_default="paid"),
    )
    bind = op.get_bind()
    order_columns = {item["name"] for item in sa.inspect(bind).get_columns("orders")}
    if "cancelled_at" in order_columns:
        bind.execute(sa.text(
            "UPDATE orders SET payment_status = 'refunded' "
            "WHERE cancelled_at IS NOT NULL AND payment_status = 'paid'"
        ))
    status_column = next(item for item in sa.inspect(bind).get_columns("orders") if item["name"] == "status")
    if not isinstance(status_column["type"], sa.Enum):
        bind.execute(sa.text(
            "UPDATE orders SET payment_status = 'pending' "
            "WHERE status = 'pending_payment' AND payment_status = 'paid'"
        ))
        bind.execute(sa.text(
            "UPDATE orders SET status = 'awaiting_sourcing' WHERE status = 'pending_payment'"
        ))
    _create_index_if_missing("ix_orders_payment_status", ["payment_status"])

    # These current runtime fields were part of the abandoned checkout-only
    # order shape but are still used by capacity and operator filtering.
    _add_column_if_missing(
        "customer_name", sa.Column("customer_name", sa.String(length=255), nullable=True)
    )
    _add_column_if_missing(
        "customer_email", sa.Column("customer_email", sa.String(length=320), nullable=True)
    )
    _add_column_if_missing(
        "assigned_build_week", sa.Column("assigned_build_week", sa.String(length=10), nullable=True)
    )
    _add_column_if_missing(
        "delivery_at_risk",
        sa.Column("delivery_at_risk", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    order_columns = {item["name"] for item in sa.inspect(bind).get_columns("orders")}
    if "customer_id" in order_columns:
        bind.execute(sa.text(
            "UPDATE orders AS o SET customer_name = c.name "
            "FROM customers AS c WHERE c.id = o.customer_id AND o.customer_name IS NULL"
        ))
        bind.execute(sa.text(
            "UPDATE orders AS o SET customer_email = c.email "
            "FROM customers AS c WHERE c.id = o.customer_id AND o.customer_email IS NULL"
        ))
    _create_index_if_missing("ix_orders_customer_email", ["customer_email"])
    _create_index_if_missing("ix_orders_assigned_build_week", ["assigned_build_week"])


def downgrade() -> None:
    bind = op.get_bind()
    remaining_states = bind.execute(sa.text(
        "SELECT count(*) FROM orders WHERE payment_status <> 'paid'"
    )).scalar_one()
    if remaining_states:
        raise RuntimeError(
            "Cannot downgrade while non-paid payment states exist; preserve refund state before rollback."
        )
    op.drop_index("ix_orders_assigned_build_week", table_name="orders")
    op.drop_index("ix_orders_customer_email", table_name="orders")
    op.drop_index("ix_orders_payment_status", table_name="orders")
    op.drop_column("orders", "delivery_at_risk")
    op.drop_column("orders", "assigned_build_week")
    op.drop_column("orders", "customer_email")
    op.drop_column("orders", "customer_name")
    op.drop_column("orders", "payment_status")
