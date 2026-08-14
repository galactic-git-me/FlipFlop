#!/usr/bin/env python3
"""
Backfill existing listings with enhanced component specs.
Runs the new spec extraction logic on all existing listings.
"""
import asyncio
import sys
sys.path.insert(0, 'flipflop-api')

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update
from app.config import get_settings
from app.models.listing import Listing
from app.services.spec_parser import parse_specs

async def backfill_specs():
    """Re-parse all listings with new extraction logic"""
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        # Get all listings
        result = await db.execute(select(Listing))
        listings = result.scalars().all()
        total = len(listings)

        print(f"[INFO] Backfilling {total} listings with enhanced specs...\n")

        updated_count = 0
        had_new_data = 0

        for i, listing in enumerate(listings, 1):
            if i % 100 == 0:
                print(f"[PROGRESS] {i}/{total} ({100*i//total}%)")

            # Re-parse specs with new extraction logic
            specs = parse_specs(listing.title, listing.description or "")

            # Update listing with new fields (only if we extracted something)
            made_changes = False

            if specs.ram_brand and not listing.ram_brand:
                listing.ram_brand = specs.ram_brand
                made_changes = True
            if specs.ram_model and not listing.ram_model:
                listing.ram_model = specs.ram_model
                made_changes = True
            if specs.ram_speed and not listing.ram_speed:
                listing.ram_speed = specs.ram_speed
                made_changes = True
            if specs.ram_cl and not listing.ram_cl:
                listing.ram_cl = specs.ram_cl
                made_changes = True
            if specs.ram_sticks and not listing.ram_sticks:
                listing.ram_sticks = specs.ram_sticks
                made_changes = True

            if specs.storage_brand and not listing.storage_brand:
                listing.storage_brand = specs.storage_brand
                made_changes = True
            if specs.storage_model and not listing.storage_model:
                listing.storage_model = specs.storage_model
                made_changes = True
            if specs.storage_form_factor and not listing.storage_form_factor:
                listing.storage_form_factor = specs.storage_form_factor
                made_changes = True

            if specs.psu_brand and not listing.psu_brand:
                listing.psu_brand = specs.psu_brand
                made_changes = True
            if specs.psu_wattage and not listing.psu_wattage:
                listing.psu_wattage = specs.psu_wattage
                made_changes = True
            if specs.psu_rating and not listing.psu_rating:
                listing.psu_rating = specs.psu_rating
                made_changes = True

            if specs.case_brand and not listing.case_brand:
                listing.case_brand = specs.case_brand
                made_changes = True
            if specs.case_model and not listing.case_model:
                listing.case_model = specs.case_model
                made_changes = True
            if specs.case_form_factor and not listing.case_form_factor:
                listing.case_form_factor = specs.case_form_factor
                made_changes = True
            if specs.case_color and not listing.case_color:
                listing.case_color = specs.case_color
                made_changes = True

            # Migrate has_psu to psu_included (if not already migrated)
            if hasattr(listing, 'has_psu') and listing.has_psu is not None:
                listing.psu_included = listing.has_psu
                made_changes = True

            if made_changes:
                updated_count += 1
                had_new_data += 1

        # Commit all changes
        await db.commit()

        print(f"\n[RESULTS]")
        print(f"  Total listings: {total}")
        print(f"  Updated: {updated_count}")
        print(f"  With new data: {had_new_data}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(backfill_specs())
