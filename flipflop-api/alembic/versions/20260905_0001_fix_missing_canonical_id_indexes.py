"""Actually create the indexes on gem_radar_listing_observations canonical
identifier columns (gtin, mpn, model_number, epid).

The migrations that added these columns (20260801_0006, 20260801_0007) used
`op.add_column(..., sa.Column(..., index=True))`. That `index=True` flag is
only honored by SQLAlchemy's `Base.metadata.create_all()` / autogenerate --
Alembic's `op.add_column` does not read it and never issues a `CREATE INDEX`.
So every DB that went through those migrations (rather than a fresh
`create_all()`) has these columns entirely unindexed, even though the ORM
model claims otherwise. build_batch_price_index() (app/gem_radar/pipeline.py)
queries all four columns every scan/submission over a 14-day window capped at
20,000 rows -- on a growing table these become full-column scans, which is
the primary suspect for sourcing-pipeline processing slowing down over time.

`checkfirst=True` on each create_index call makes this safe to run even if
an index with the same name already exists on some environment.

Revision ID: 20260905_0001
Revises: 20260902_0004
Create Date: 2026-09-05 00:00:00.000000
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260905_0001"
down_revision = "20260902_0004"
branch_labels = None
depends_on = None

_TABLE = "gem_radar_listing_observations"
_COLUMNS = ("gtin", "mpn", "model_number", "epid")


def _existing_index_names(conn) -> set[str]:
    from sqlalchemy import inspect

    inspector = inspect(conn)
    return {ix["name"] for ix in inspector.get_indexes(_TABLE)}


def upgrade() -> None:
    conn = op.get_bind()
    existing = _existing_index_names(conn)
    for column in _COLUMNS:
        index_name = f"ix_{_TABLE}_{column}"
        if index_name in existing:
            continue
        op.create_index(index_name, _TABLE, [column])


def downgrade() -> None:
    conn = op.get_bind()
    existing = _existing_index_names(conn)
    for column in _COLUMNS:
        index_name = f"ix_{_TABLE}_{column}"
        if index_name in existing:
            op.drop_index(index_name, table_name=_TABLE)
