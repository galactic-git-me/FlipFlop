"""Run the resumable catalogue-copy sweep using local/free LLM tiers only."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import AsyncSessionLocal, engine
from app.services.catalogue_marketing_copy import generate_next_marketing_copy_batch


async def main() -> int:
    batch_number = 0
    try:
        while True:
            async with AsyncSessionLocal() as db:
                result = await generate_next_marketing_copy_batch(db, 4)
                await db.commit()
            batch_number += 1
            print(json.dumps({"batch": batch_number, **result}, ensure_ascii=False), flush=True)
            if result.get("failed"):
                return 1
            if result.get("remaining", 0) == 0 or result.get("attempted", 0) == 0:
                return 0
    except Exception as exc:
        print(json.dumps({"batch": batch_number + 1, "error": str(exc)[:500]}), flush=True)
        return 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
