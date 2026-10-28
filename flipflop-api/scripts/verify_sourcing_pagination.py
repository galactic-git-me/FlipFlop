"""Read-only check of the sourcing listing pages against the current database.

Run from flipflop-api: python -m scripts.verify_sourcing_pagination
"""
import asyncio

from app.api.gem_radar import get_scored_listings_latest_run, get_source_activity, get_scored_listings_facets
from app.database import AsyncSessionLocal, engine


async def main() -> None:
    try:
        async with AsyncSessionLocal() as db:
            filters = dict(category="cpu", classification="all", stock_lane="all", title_query=None, sort_key="deal_score", sort_dir="desc")
            first = await get_scored_listings_latest_run(environment="DEV", offset=0, paged=True, limit=2, db=db, _=None, **filters)
            second = await get_scored_listings_latest_run(environment="DEV", offset=2, paged=True, limit=2, db=db, _=None, **filters)
            assert isinstance(first, dict) and isinstance(second, dict)
            assert first["has_more"] and len(first["items"]) == 2
            assert {item["listing_id"] for item in first["items"]}.isdisjoint(
                {item["listing_id"] for item in second["items"]}
            )
            assert all(item["category"] == "cpu" for item in first["items"] + second["items"])
            facets = await get_scored_listings_facets(db=db, _=None)
            assert facets["categories"]["cpu"] >= first["total"]
            activity = await get_source_activity(db=db, _=None)
            assert isinstance(activity, dict)
            print(f"PASS: CPU pages distinct; global CPU count={facets['categories']['cpu']}; {len(activity)} vendors with last-observed data")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
