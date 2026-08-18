"""Continuous bounded-retention maintenance for high-volume worker tables."""

import asyncio

import structlog
from sqlalchemy import text

from app.database import AsyncSessionLocal


log = structlog.get_logger()

RETENTION = (
    ("gem_radar_decision_events", "created_at", "72 hours"),
    ("gem_radar_listing_demand_history", "observed_at", "48 hours"),
    ("submission_queue", "created_at", "7 days"),
    ("gem_radar_listing_observations", "observed_at", "30 days"),
    ("gem_radar_scored_listings", "scored_at", "30 days"),
)


async def _delete_batch(table: str, timestamp_column: str, retention: str) -> int:
    # Table/column/interval values come only from the constant allow-list above.
    statement = text(
        f"""
        DELETE FROM {table}
        WHERE id IN (
            SELECT id FROM {table}
            WHERE {timestamp_column} < now() - interval '{retention}'
            ORDER BY id
            LIMIT 5000
        )
        """
    )
    async with AsyncSessionLocal() as db:
        result = await db.execute(statement)
        await db.commit()
        return result.rowcount or 0


async def run_database_cleaner(interval_seconds: int = 3600) -> None:
    """Continuously prune expired telemetry without long table locks."""
    while True:
        try:
            totals: dict[str, int] = {}
            for table, column, retention in RETENTION:
                deleted = 0
                while True:
                    count = await _delete_batch(table, column, retention)
                    deleted += count
                    if count < 5000:
                        break
                    await asyncio.sleep(0.25)
                totals[table] = deleted
            log.info("database_cleaner.completed", deleted=totals)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("database_cleaner.failed", error=str(exc))
        await asyncio.sleep(interval_seconds)
