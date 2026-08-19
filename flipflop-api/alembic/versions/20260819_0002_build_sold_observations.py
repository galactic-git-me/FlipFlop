"""Persist extension-collected complete-build sold comparables."""

from alembic import op
import sqlalchemy as sa

revision = "20260819_0002"
down_revision = "20260819_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "build_sold_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("build_id", sa.Integer(), sa.ForeignKey("manual_builds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=1000), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("postage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("condition", sa.String(length=20), nullable=False, server_default="used"),
        sa.Column("sold_at", sa.String(length=50), nullable=True),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("match_basis", sa.String(length=255), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_build_sold_observations_build_id", "build_sold_observations", ["build_id"])
    op.create_index("ix_build_sold_observations_observed_at", "build_sold_observations", ["observed_at"])
    op.create_index("ix_build_sold_obs_build_time", "build_sold_observations", ["build_id", "observed_at"])
    op.create_index("uq_build_sold_obs_build_url", "build_sold_observations", ["build_id", "source_url"], unique=True)


def downgrade() -> None:
    op.drop_table("build_sold_observations")
