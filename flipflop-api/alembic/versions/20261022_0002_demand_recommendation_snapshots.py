"""Persist immutable demand recommendation and blocker snapshots."""
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

revision = "20261022_0002"
down_revision = "20261022_0001"
branch_labels = None
depends_on = None


def upgrade():
    _create_table_if_missing(
        "demand_recommendation_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assessment_id", sa.String(36), nullable=False),
        sa.Column("cell_id", sa.String(64), nullable=False),
        sa.Column("definition_sha256", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("delivery_mode", sa.String(32), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_by_admin_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "assessment_id", "cell_id", "channel", "delivery_mode",
            name="uq_demand_recommendation_assessment_cell_channel_mode",
        ),
    )
    _create_index_if_missing("ix_demand_recommendation_snapshots_assessment_id", "demand_recommendation_snapshots", ["assessment_id"])
    _create_index_if_missing("ix_demand_recommendation_snapshots_cell_id", "demand_recommendation_snapshots", ["cell_id"])


def downgrade():
    raise RuntimeError("Preserve immutable demand decision history when rolling back application code")
