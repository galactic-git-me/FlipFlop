"""Requeue only the two diagnosed schema failures; dry-run by default."""
import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine
from app.gem_radar.schema_guard import require_scan_schema


async def recover(apply: bool):
    try:
        async with AsyncSessionLocal() as db:
            await require_scan_schema(db)
            rows = (await db.execute(text("""
                SELECT id, retry_count, last_error FROM submission_queue
                WHERE status='failed'
                  AND last_error LIKE '%UndefinedColumnError%'
                  AND (last_error LIKE '%gem_radar_listing_observations.image_urls%'
                       OR last_error LIKE '%gem_radar_listing_observations.commercial_source_evidence%')
                ORDER BY id FOR UPDATE
            """))).mappings().all()
            print(f"Recoverable schema-failed batches: {len(rows)}")
            if not apply or not rows:
                return
            backup = Path(__file__).resolve().parents[2] / "logs" / (
                "scan-schema-recovery-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
            backup.parent.mkdir(exist_ok=True)
            backup.write_text(json.dumps([dict(row) for row in rows], indent=2), encoding="utf-8")
            await db.execute(text("""
                UPDATE submission_queue SET status='pending', retry_count=0,
                    completed_at=NULL WHERE id=ANY(:ids) AND status='failed'
            """), {"ids": [row["id"] for row in rows]})
            # The failed queue previously looked drained, so Phase 2 may
            # already have cleared the sweep flag. Re-arm classification.
            await db.execute(text("""
                INSERT INTO gem_radar_sweep_signal (id, pending)
                VALUES (1, TRUE) ON CONFLICT (id) DO UPDATE SET pending=TRUE
            """))
            await db.commit()
            print(f"Requeued {len(rows)} batches; previous errors retained. Audit: {backup}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(recover(parser.parse_args().apply))
