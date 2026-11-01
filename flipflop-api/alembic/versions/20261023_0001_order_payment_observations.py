"""Add immutable Stripe payment and refund observations."""
from alembic import op
import sqlalchemy as sa


def _create_table_if_missing(name, *elements):
    # Runtime startup may have created current ORM tables before Alembic catches up.
    if not sa.inspect(op.get_bind()).has_table(name):
        op.create_table(name, *elements)


def _create_index_if_missing(name, table_name, columns):
    indexes = sa.inspect(op.get_bind()).get_indexes(table_name)
    if name not in {index["name"] for index in indexes}:
        op.create_index(name, table_name, columns)

revision = "20261023_0001"
down_revision = "20261022_0003"
branch_labels = None
depends_on = None


def upgrade():
    _create_table_if_missing(
        "order_payment_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stripe_event_id", sa.String(100), nullable=False, unique=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("order_id", sa.Integer(), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("payment_intent_id", sa.String(100), nullable=True),
        sa.Column("charge_id", sa.String(100), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("amount_refunded_minor", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("stripe_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_index_if_missing("ix_order_payment_observations_order_created", "order_payment_observations", ["order_id", "created_at"])
    _create_index_if_missing("ix_order_payment_observations_intent_created", "order_payment_observations", ["payment_intent_id", "created_at"])


def downgrade():
    raise RuntimeError("Preserve immutable Stripe reconciliation history when rolling back application code")
