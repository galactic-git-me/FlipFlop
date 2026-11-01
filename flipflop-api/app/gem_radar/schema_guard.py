"""Block queue claims when scan models and the database disagree."""
from sqlalchemy import inspect

from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.submission_queue import SubmissionQueue


def check_scan_schema(connection):
    inspector = inspect(connection)
    missing = []
    for model in (GemRadarListingObservation, GemRadarScoredListing, SubmissionQueue):
        table = model.__table__
        actual = {column["name"] for column in inspector.get_columns(table.name)} if inspector.has_table(table.name) else set()
        missing.extend(f"{table.name}.{column.name}" for column in table.columns if column.name not in actual)
    if missing:
        raise RuntimeError("Gem Radar schema incompatible; apply database migrations before scanning. Missing: " + ", ".join(missing))


async def require_scan_schema(db):
    connection = await db.connection()
    await connection.run_sync(check_scan_schema)
