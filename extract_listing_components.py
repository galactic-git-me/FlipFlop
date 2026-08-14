#!/usr/bin/env python3
"""
Extract components from actual listings data in FlipFlop database.
"""
import asyncio
import csv
from pathlib import Path
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import json

import sys
sys.path.insert(0, 'flipflop-api')

from app.config import get_settings
from app.models.listing import Listing

async def extract_from_listings():
    """Extract component data from listings"""

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("[INFO] Connecting to database...")

        # Get counts by component type
        # Listings have structured component columns: cpu, gpu, ram_gb, storage_gb, etc.

        # CPU listings
        cpu_result = await db.execute(
            select(func.count()).select_from(Listing).where(Listing.cpu.isnot(None))
        )
        cpu_count = cpu_result.scalar() or 0

        # GPU listings
        gpu_result = await db.execute(
            select(func.count()).select_from(Listing).where(Listing.gpu.isnot(None))
        )
        gpu_count = gpu_result.scalar() or 0

        # RAM listings
        ram_result = await db.execute(
            select(func.count()).select_from(Listing).where(Listing.ram_gb.isnot(None))
        )
        ram_count = ram_result.scalar() or 0

        # Storage listings
        storage_result = await db.execute(
            select(func.count()).select_from(Listing).where(Listing.storage_gb.isnot(None))
        )
        storage_count = storage_result.scalar() or 0

        # Total listings
        total_result = await db.execute(
            select(func.count()).select_from(Listing)
        )
        total_count = total_result.scalar() or 0

        # Get distinct CPU models
        cpu_models = await db.execute(
            select(Listing.cpu, func.count(Listing.id).label('count'))
            .where(Listing.cpu.isnot(None))
            .group_by(Listing.cpu)
            .order_by(func.count(Listing.id).desc())
            .limit(50)
        )
        cpus = cpu_models.fetchall()

        # Get distinct GPU models
        gpu_models = await db.execute(
            select(Listing.gpu, func.count(Listing.id).label('count'))
            .where(Listing.gpu.isnot(None))
            .group_by(Listing.gpu)
            .order_by(func.count(Listing.id).desc())
            .limit(50)
        )
        gpus = gpu_models.fetchall()

        # Prepare output
        rows = []

        # Add CPU entries
        for cpu, count in cpus:
            rows.append({
                'component_type': 'CPU',
                'component_model': cpu or 'Unknown',
                'listing_count': count or 0
            })

        # Add GPU entries
        for gpu, count in gpus:
            rows.append({
                'component_type': 'GPU',
                'component_model': gpu or 'Unknown',
                'listing_count': count or 0
            })

        # Write CSV
        csv_path = Path('flipflop-component-listings.csv')
        fieldnames = ['component_type', 'component_model', 'listing_count']

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        # Summary
        print(f"\n[RESULTS] Component Listings Summary")
        print(f"  Total listings in database: {total_count}")
        print(f"  Listings with CPU: {cpu_count}")
        print(f"  Listings with GPU: {gpu_count}")
        print(f"  Listings with RAM: {ram_count}")
        print(f"  Listings with Storage: {storage_count}")
        print(f"\n  Output: {csv_path.resolve()}")

        print(f"\n[TOP CPUs] (top 20 by listing count)")
        print(f"  {'Model':<50} {'Listings':>10}")
        print(f"  {'-'*62}")
        for i, (cpu, count) in enumerate(cpus[:20]):
            print(f"  {str(cpu):<50} {count:>10}")

        print(f"\n[TOP GPUs] (top 20 by listing count)")
        print(f"  {'Model':<50} {'Listings':>10}")
        print(f"  {'-'*62}")
        for i, (gpu, count) in enumerate(gpus[:20]):
            print(f"  {str(gpu):<50} {count:>10}")

        print(f"\n[DISTINCT MODELS]")
        print(f"  CPU models: {len(cpus)}")
        print(f"  GPU models: {len(gpus)}")
        print(f"  Total in CSV: {len(rows)}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(extract_from_listings())
