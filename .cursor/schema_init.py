"""Initialise the Gem Radar dev database schema.

The standalone Gem Radar API (``app.gem_radar_standalone``) only runs
``app.database.Base.metadata.create_all`` at startup. That misses two things a
fresh Postgres database needs before the admin Sourcing Dashboard works:

1. ``submission_queue`` lives on a *second* declarative base
   (``app.models.base.Base``) that the standalone never creates, so the queue
   endpoints 500 with ``relation "submission_queue" does not exist``.
2. Several columns on ``gem_radar_scored_listings`` (``market_lower_price``,
   ``market_median_price``, ``market_upper_price``, ``pct_offset``,
   ``recommendation``) are added in production via raw ``ALTER`` (see
   ``app/gem_radar/phase2_runner.py``) and read back through raw SQL, but are
   not declared on the ORM model — so ``create_all`` never makes them.

This script creates both metadata sets and ensures those raw columns exist. It
is idempotent (``create_all`` and ``ADD COLUMN IF NOT EXISTS``), so it is safe
to run on every environment install.
"""
from __future__ import annotations

import os

os.environ.setdefault("OLLAMA_MODEL", "disabled")

from sqlalchemy import create_engine, text

from app.config import get_settings
import app.models  # noqa: F401 — registers every ORM model on both bases
from app.database import Base as DbBase
from app.models.base import Base as ModelsBase

RAW_COLUMNS = {
    "market_lower_price": "double precision",
    "market_median_price": "double precision",
    "market_upper_price": "double precision",
    "pct_offset": "double precision",
    "recommendation": "varchar(50)",
}


def main() -> None:
    engine = create_engine(get_settings().sync_database_url)
    for name, base in (("app.database.Base", DbBase), ("app.models.base.Base", ModelsBase)):
        base.metadata.create_all(engine)
        print(f"{name}: {len(base.metadata.tables)} tables ensured")

    with engine.begin() as conn:
        for column, coltype in RAW_COLUMNS.items():
            conn.execute(
                text(
                    "ALTER TABLE gem_radar_scored_listings "
                    f"ADD COLUMN IF NOT EXISTS {column} {coltype}"
                )
            )
    print("raw ALTER columns ensured: " + ", ".join(RAW_COLUMNS))
    engine.dispose()
    print("SCHEMA_INIT_DONE")


if __name__ == "__main__":
    main()
