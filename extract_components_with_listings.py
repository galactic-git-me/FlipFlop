#!/usr/bin/env python3
"""
Extract distinct components by type with listing counts from FlipFlop database.
Queries the actual database for live data.
"""
import asyncio
import csv
from pathlib import Path
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Import models
import sys
sys.path.insert(0, 'flipflop-api')

from app.config import get_settings
from app.models.component_catalogue import Component
from app.models.listing import Listing
from app.database import Base

async def extract_components_with_listings():
    """Extract distinct components and count their listings"""

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("[INFO] Connecting to database...")

        # Get all distinct components
        result = await db.execute(
            select(Component.category, Component.manufacturer, Component.model,
                   Component.variant, func.count(Component.id).label('count'))
            .group_by(Component.category, Component.manufacturer, Component.model, Component.variant)
            .order_by(Component.category, Component.manufacturer, Component.model)
        )

        components = result.fetchall()

        print(f"[INFO] Found {len(components)} distinct components")

        # Extract data
        rows = []
        total_listings = 0

        for comp in components:
            category, manufacturer, model, variant, count = comp
            rows.append({
                'category': category or 'N/A',
                'manufacturer': manufacturer or 'N/A',
                'model': model or 'N/A',
                'variant': variant or '',
                'component_count': count or 0
            })
            total_listings += (count or 0)

        # Write CSV
        csv_path = Path('flipflop-components-with-listings.csv')
        fieldnames = ['category', 'manufacturer', 'model', 'variant', 'component_count']

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        # Summary
        print(f"\n[RESULTS]")
        print(f"  Total distinct components: {len(rows)}")
        print(f"  Total component listings: {total_listings}")
        print(f"  Output: {csv_path.resolve()}")

        # Summary by category
        by_category = {}
        for row in rows:
            cat = row['category']
            count = row['component_count']
            if cat not in by_category:
                by_category[cat] = {'components': 0, 'listings': 0}
            by_category[cat]['components'] += 1
            by_category[cat]['listings'] += count

        print(f"\n[SUMMARY] By Category:")
        print(f"  {'Category':<30} {'Components':>12} {'Listings':>12}")
        print(f"  {'-'*56}")
        for cat in sorted(by_category.keys()):
            stats = by_category[cat]
            print(f"  {cat:<30} {stats['components']:>12} {stats['listings']:>12}")
        print(f"  {'-'*56}")
        print(f"  {'TOTAL':<30} {len(rows):>12} {total_listings:>12}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(extract_components_with_listings())
