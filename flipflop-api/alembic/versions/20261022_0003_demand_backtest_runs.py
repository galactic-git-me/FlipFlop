"""Persist append-only time-split replay results."""
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

revision = "20261022_0003"
down_revision = "20261022_0002"
branch_labels = None
depends_on = None


def upgrade():
    _create_table_if_missing(
        "demand_backtest_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("training_cutoff", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    _create_index_if_missing("ix_demand_backtest_runs_created_at", "demand_backtest_runs", ["created_at"])


def downgrade():
    raise RuntimeError("Preserve immutable demand backtest audit history when rolling back application code")
