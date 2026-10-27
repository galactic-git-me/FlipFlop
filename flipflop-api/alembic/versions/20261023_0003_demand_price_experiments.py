"""Persist bounded demand price experiments and stable arm assignments."""
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

revision = "20261023_0003"
down_revision = "20261023_0002"
branch_labels = None
depends_on = None


def upgrade():
    _create_table_if_missing(
        "demand_price_experiments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cell_id", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("delivery_mode", sa.String(32), nullable=False),
        sa.Column("control_price_gbp", sa.String(16), nullable=False),
        sa.Column("treatment_price_gbp", sa.String(16), nullable=False),
        sa.Column("floor_price_gbp", sa.String(16), nullable=False),
        sa.Column("max_assignments", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("approval", sa.JSON(), nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
    )
    _create_index_if_missing("ix_demand_price_experiments_cell_id", "demand_price_experiments", ["cell_id"])
    _create_table_if_missing(
        "demand_price_experiment_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("experiment_id", sa.String(36), nullable=False),
        sa.Column("subject_fingerprint", sa.String(64), nullable=False),
        sa.Column("arm", sa.String(16), nullable=False),
        sa.Column("assigned_price_gbp", sa.String(16), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("experiment_id", "subject_fingerprint", name="uq_demand_experiment_subject"),
    )
    _create_index_if_missing("ix_demand_price_experiment_assignments_experiment_id", "demand_price_experiment_assignments", ["experiment_id"])


def downgrade():
    raise RuntimeError("Preserve demand experiment history when rolling back application code")
