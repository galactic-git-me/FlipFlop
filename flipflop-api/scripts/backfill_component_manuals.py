"""One-off, resumable initial capture of official manuals for active Playbook parts."""
from __future__ import annotations

import asyncio

from app.database import AsyncSessionLocal, engine
from app.services.component_manual_discovery import discover_playbook_component_manuals


async def main() -> None:
    batch_size = 5
    total_attempted = total_downloaded = 0
    try:
        async with AsyncSessionLocal() as db:
            while True:
                result = await discover_playbook_component_manuals(db, batch_size=batch_size)
                total_attempted += int(result["attempted"])
                total_downloaded += int(result["downloaded"])
                print({"attempted": total_attempted, "downloaded": total_downloaded,
                       "last_batch_not_found": len(result["not_found"]),
                       "deferred": result["deferred"]}, flush=True)
                if result.get("search_unavailable"):
                    print("Search provider returned 403/429; run again after its retry window or use browser search.", flush=True)
                    break
                if result["attempted"] < batch_size:
                    break
                await asyncio.sleep(2)
        print({"complete": True, "attempted": total_attempted, "downloaded": total_downloaded}, flush=True)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
