#!/usr/bin/env python3
"""Fix the corrupted listing price"""
import asyncio
from sqlalchemy import select, update
from app.database import AsyncSessionLocal
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_observation import GemRadarListingObservation

async def fix_listing():
    listing_id = "407119703791"
    correct_price = 317.0  # The actual eBay price

    async with AsyncSessionLocal() as db:
        # Update scored listing
        stmt = update(GemRadarScoredListing).where(
            GemRadarScoredListing.listing_id == listing_id
        ).values(
            delivered_price=correct_price,
            actual_listing_price=correct_price,
            postage_price=0.0
        )
        result = await db.execute(stmt)
        print(f"Updated {result.rowcount} scored listing rows")

        # Update observations
        stmt = update(GemRadarListingObservation).where(
            GemRadarListingObservation.listing_id == listing_id
        ).values(
            delivered_price=correct_price,
            item_price=correct_price,
            postage_price=0.0
        )
        result = await db.execute(stmt)
        print(f"Updated {result.rowcount} observation rows")

        await db.commit()
        print(f"\n✓ Fixed listing {listing_id}: Price now £{correct_price}")

        # Verify the fix
        stmt = select(GemRadarScoredListing).where(
            GemRadarScoredListing.listing_id == listing_id
        ).order_by(GemRadarScoredListing.scored_at.desc())
        result = await db.execute(stmt)
        scored = result.scalars().first()
        if scored:
            print(f"\nVerification:")
            print(f"  Listing ID: {scored.listing_id}")
            print(f"  Delivered Price: £{scored.delivered_price}")
            print(f"  Item Price: £{scored.actual_listing_price}")

asyncio.run(fix_listing())
