"""Read-only check of the sourcing listing pages against the current database.

Run from flipflop-api: python -m scripts.verify_sourcing_pagination
"""
import asyncio

from app.api.gem_radar import get_scored_listings_latest_run, get_source_activity
from app.database import AsyncSessionLocal, engine


async def main() -> None:
    try:
        async with AsyncSessionLocal() as db:
            first = await get_scored_listings_latest_run(environment="DEV", offset=0, paged=True, limit=2, db=db, _=None)
            second = await get_scored_listings_latest_run(environment="DEV", offset=2, paged=True, limit=2, db=db, _=None)
            assert isinstance(first, dict) and isinstance(second, dict)
            assert first["has_more"] and len(first["items"]) == 2
            assert {item["listing_id"] for item in first["items"]}.isdisjoint(
                {item["listing_id"] for item in second["items"]}
            )
            activity = await get_source_activity(db=db, _=None)
            assert isinstance(activity, dict)
            print(f"PASS: two distinct pages; {len(activity)} vendors with last-observed data")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
