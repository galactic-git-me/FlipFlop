"""Plan or generate product-specific models using catalogue listing photos.

Default is a read-only plan. Pass --generate and explicit --variant IDs to
create reviewable drafts; no generated model is automatically activated.
"""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import select
from app.database import AsyncSessionLocal, engine
from app.models.catalogue import CatalogueVariant, PlaybookSlot
from app.models.listing import Listing
from app.services.listing_3d_references import select_listing_references


async def main(args):
    try:
        async with AsyncSessionLocal() as db:
            query = (select(CatalogueVariant, Listing, PlaybookSlot)
                     .join(Listing, CatalogueVariant.listing_id == Listing.id)
                     .join(PlaybookSlot, CatalogueVariant.slot_id == PlaybookSlot.id)
                     .where(CatalogueVariant.status == "active", PlaybookSlot.slot_type != "os")
                     .order_by(CatalogueVariant.id))
            if args.variant:
                query = query.where(CatalogueVariant.id.in_(args.variant))
            rows = (await db.execute(query)).all()
            if not rows:
                print("No matching active catalogue variants in this database; nothing generated.", flush=True)
            for variant, listing, slot in rows:
                try:
                    images = select_listing_references(listing.image_urls)
                except ValueError as exc:
                    print(json.dumps(dict(variant_id=variant.id, skipped=str(exc))), flush=True)
                    continue
                print(json.dumps(dict(variant_id=variant.id, listing_id=listing.id,
                    category=slot.slot_type, title=listing.title, images=images)), flush=True)
                if args.generate:
                    from app.api.assets_admin import generate_listing_variant_asset, ListingAssetRequest
                    asset = await generate_listing_variant_asset(variant.id,
                        ListingAssetRequest(image_urls=images), SimpleNamespace(email="listing-photo-generation"), db)
                    print(json.dumps(dict(asset_id=asset["id"], status=asset["status"])), flush=True)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=int, action="append")
    parser.add_argument("--generate", action="store_true")
    args = parser.parse_args()
    if args.generate and not args.variant:
        parser.error("--generate requires explicit --variant IDs")
    asyncio.run(main(args))
