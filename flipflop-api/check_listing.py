#!/usr/bin/env python3
"""Check listing price in database"""
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_observation import GemRadarListingObservation

async def check_listing():
    listing_id = "407119703791"

    async with AsyncSessionLocal() as db:
        # Check scored listings (most recent)
        stmt = select(GemRadarScoredListing).where(
            GemRadarScoredListing.listing_id == listing_id
        ).order_by(GemRadarScoredListing.scored_at.desc())
        result = await db.execute(stmt)
        scored = result.scalars().first()

        if scored:
            print("=== SCORED LISTING (Most Recent) ===")
            print(f"Title: {scored.title}")
            print(f"Listing ID: {scored.listing_id}")
            print(f"Delivered Price: £{scored.delivered_price}")
            print(f"Item Price: £{scored.actual_listing_price}")
            print(f"Postage Price: £{scored.postage_price}")
            print(f"Category: {scored.category}")
            print(f"Classification: {scored.classification}")
            print(f"URL: {scored.url}")
            print(f"Scored At: {scored.scored_at}")
        else:
            print("No scored listing found")

        # Check observations
        stmt = select(GemRadarListingObservation).where(
            GemRadarListingObservation.listing_id == listing_id
        ).order_by(GemRadarListingObservation.observed_at.desc())
        result = await db.execute(stmt)
        obs = result.scalars().first()

        if obs:
            print("\n=== LATEST OBSERVATION ===")
            print(f"Title: {obs.title}")
            print(f"Delivered Price: £{obs.delivered_price}")
            print(f"Item Price: £{obs.item_price}")
            print(f"Postage Price: £{obs.postage_price}")
            print(f"Observed: {obs.observed_at}")

asyncio.run(check_listing())
