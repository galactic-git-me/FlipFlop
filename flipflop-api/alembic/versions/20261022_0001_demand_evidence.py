"""Add immutable demand evidence without changing existing ingestion tables."""
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

revision = "20261022_0001"
down_revision = "20261020_0001"
branch_labels = None
depends_on = None


def upgrade():
    _create_table_if_missing("demand_evidence_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("deduplication_key", sa.String(160), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("captured_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_id", "deduplication_key", name="uq_demand_evidence_source_key"))
    _create_index_if_missing("ix_demand_evidence_snapshots_source_id", "demand_evidence_snapshots", ["source_id"])
    _create_index_if_missing("ix_demand_evidence_snapshots_dataset", "demand_evidence_snapshots", ["dataset"])
    _create_table_if_missing("demand_source_permissions",
        sa.Column("source_id", sa.String(64), primary_key=True),
        sa.Column("access_scope", sa.String(24), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("evidence_reference", sa.String(1000), nullable=False),
        sa.Column("commercial_use_confirmed", sa.Boolean(), nullable=False),
        sa.Column("reviewed_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True))


def downgrade():
    raise RuntimeError("Preserve imported audit evidence when rolling back application code")
