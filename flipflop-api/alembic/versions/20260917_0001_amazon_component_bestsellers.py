"""Store daily Amazon bestseller ranks for every component category."""
from alembic import op
import sqlalchemy as sa


revision = "20260917_0001"
down_revision = "20260916_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "amazon_bestseller_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("list_name", sa.String(length=200), nullable=False),
        sa.Column("asin", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=True),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("cpk", sa.String(length=64), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("review_count", sa.Integer(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_amazon_bestseller_observations_category", "amazon_bestseller_observations", ["category"])
    op.create_index("ix_amazon_bestseller_observations_asin", "amazon_bestseller_observations", ["asin"])
    op.create_index("ix_amazon_bestseller_observations_cpk", "amazon_bestseller_observations", ["cpk"])
    op.create_index("ix_amazon_bestseller_observations_captured_at", "amazon_bestseller_observations", ["captured_at"])
    op.create_index("ix_amazon_bestseller_obs_cpk_time", "amazon_bestseller_observations", ["cpk", "captured_at"])
    op.create_index("ix_amazon_bestseller_obs_category_rank", "amazon_bestseller_observations", ["category", "rank"])


def downgrade() -> None:
    op.drop_index("ix_amazon_bestseller_obs_category_rank", table_name="amazon_bestseller_observations")
    op.drop_index("ix_amazon_bestseller_obs_cpk_time", table_name="amazon_bestseller_observations")
    op.drop_index("ix_amazon_bestseller_observations_captured_at", table_name="amazon_bestseller_observations")
    op.drop_index("ix_amazon_bestseller_observations_cpk", table_name="amazon_bestseller_observations")
    op.drop_index("ix_amazon_bestseller_observations_asin", table_name="amazon_bestseller_observations")
    op.drop_index("ix_amazon_bestseller_observations_category", table_name="amazon_bestseller_observations")
    op.drop_table("amazon_bestseller_observations")
