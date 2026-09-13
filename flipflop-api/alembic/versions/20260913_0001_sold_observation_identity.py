"""Keep sold-comparable identity evidence for safe reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "20260913_0001"
down_revision = "20260908_0001"
branch_labels = None
depends_on = None

def upgrade() -> None:
    table = "gem_radar_sold_observations"
    for name, column in (
        ("title", sa.String(500)),
        ("canonical_item_id", sa.String(255)),
        ("brand", sa.String(100)),
        ("model", sa.String(255)),
        ("mpn", sa.String(255)),
        ("gtin", sa.String(64)),
        ("identity_confidence", sa.Float()),
    ):
        op.add_column(table, sa.Column(name, column, nullable=True))
    op.create_index("ix_gem_radar_sold_observations_canonical_item_id", table, ["canonical_item_id"])
    # Existing collector rows already carry the marketplace URL. Promote it
    # to a bounded stable deduplication key without inventing identity for
    # rows that have no URL.
    op.execute(sa.text(
        "UPDATE gem_radar_sold_observations "
        "SET canonical_item_id = CASE WHEN length(source_url) <= 255 "
        "THEN source_url ELSE left(source_url, 190) || ':' || md5(source_url) END "
        "WHERE canonical_item_id IS NULL AND source_url IS NOT NULL"
    ))

def downgrade() -> None:
    table = "gem_radar_sold_observations"
    op.drop_index("ix_gem_radar_sold_observations_canonical_item_id", table_name=table)
    for name in ("identity_confidence", "gtin", "mpn", "model", "brand", "canonical_item_id", "title"):
        op.drop_column(table, name)
