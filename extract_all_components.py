#!/usr/bin/env python3
"""
Extract ALL components from FlipFlop database into a single comprehensive CSV.
Explains why RAM/Storage/Cases have different data structures.
"""
import asyncio
import csv
from pathlib import Path
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import json

import sys
sys.path.insert(0, 'flipflop-api')

from app.config import get_settings
from app.models.listing import Listing

async def extract_all_components():
    """Extract all component types from listings"""

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as db:
        print("[INFO] Extracting all components from database...\n")

        rows = []

        # =====================================================================
        # CPU COMPONENTS
        # =====================================================================
        cpu_models = await db.execute(
            select(Listing.cpu, func.count(Listing.id).label('count'))
            .where(Listing.cpu.isnot(None))
            .group_by(Listing.cpu)
            .order_by(func.count(Listing.id).desc())
        )
        cpus = cpu_models.fetchall()

        for cpu, count in cpus:
            rows.append({
                'component_type': 'CPU',
                'manufacturer': '[Parsed from title]',
                'model': cpu or 'Unknown',
                'variant': '',
                'spec_detail': '',
                'listing_count': count or 0,
                'notes': 'Stored as: Listing.cpu (String)'
            })

        # =====================================================================
        # GPU COMPONENTS
        # =====================================================================
        gpu_models = await db.execute(
            select(Listing.gpu, func.count(Listing.id).label('count'))
            .where(Listing.gpu.isnot(None))
            .group_by(Listing.gpu)
            .order_by(func.count(Listing.id).desc())
        )
        gpus = gpu_models.fetchall()

        for gpu, count in gpus:
            rows.append({
                'component_type': 'GPU',
                'manufacturer': '[Parsed from title]',
                'model': gpu or 'Unknown',
                'variant': '',
                'spec_detail': '',
                'listing_count': count or 0,
                'notes': 'Stored as: Listing.gpu (String)'
            })

        # =====================================================================
        # RAM COMPONENTS - BY CAPACITY (NOT MODEL)
        # =====================================================================
        print("[INFO] RAM: Stored as numeric capacity only (ram_gb: Integer)")
        ram_capacities = await db.execute(
            select(Listing.ram_gb, Listing.ram_type, func.count(Listing.id).label('count'))
            .where(Listing.ram_gb.isnot(None))
            .group_by(Listing.ram_gb, Listing.ram_type)
            .order_by(func.count(Listing.id).desc())
        )
        rams = ram_capacities.fetchall()

        for ram_gb, ram_type, count in rams:
            rows.append({
                'component_type': 'RAM',
                'manufacturer': '[Not tracked in Listing]',
                'model': f'{ram_gb}GB',
                'variant': ram_type or 'Unknown type',
                'spec_detail': f'{ram_gb}GB {ram_type or ""}',
                'listing_count': count or 0,
                'notes': 'NUMERIC only - no model names tracked. ram_type may be DDR3/DDR4/DDR5'
            })

        # =====================================================================
        # STORAGE COMPONENTS - BY CAPACITY (NOT MODEL)
        # =====================================================================
        print("[INFO] Storage: Stored as numeric capacity only (storage_gb: Integer)")
        storage_capacities = await db.execute(
            select(Listing.storage_gb, Listing.storage_type, func.count(Listing.id).label('count'))
            .where(Listing.storage_gb.isnot(None))
            .group_by(Listing.storage_gb, Listing.storage_type)
            .order_by(func.count(Listing.id).desc())
        )
        storages = storage_capacities.fetchall()

        for storage_gb, storage_type, count in storages:
            rows.append({
                'component_type': 'Storage',
                'manufacturer': '[Not tracked in Listing]',
                'model': f'{storage_gb}GB',
                'variant': storage_type or 'Unknown type',
                'spec_detail': f'{storage_gb}GB {storage_type or ""}',
                'listing_count': count or 0,
                'notes': 'NUMERIC only - no model names tracked. storage_type may be SSD/HDD/NVMe'
            })

        # =====================================================================
        # PC CASES - EXTRACTED FROM TITLE/RAW_SPECS
        # =====================================================================
        print("[INFO] Cases: Not structured in Listing model - checking title/raw_specs...")

        # Look for case-related keywords in titles
        case_keywords = ['case', 'chassis', 'tower', 'atx', 'matx', 'itx', 'cube']
        case_listings = await db.execute(
            select(func.count(Listing.id)).select_from(Listing)
            .where(or_(*[Listing.title.ilike(f'%{kw}%') for kw in case_keywords]))
        )
        case_count = case_listings.scalar() or 0

        rows.append({
            'component_type': 'PC Case',
            'manufacturer': '[Not structured - in title only]',
            'model': '[Various case models found in titles]',
            'variant': '',
            'spec_detail': '',
            'listing_count': case_count,
            'notes': 'NOT tracked as structured field. Case data is in title text only. Would need text parsing to extract distinct models.'
        })

        # =====================================================================
        # PSU COMPONENTS - AS BOOLEAN
        # =====================================================================
        print("[INFO] PSU: Tracked as boolean only (has_psu: Boolean)")
        psu_listings = await db.execute(
            select(func.count(Listing.id)).select_from(Listing)
            .where(Listing.has_psu == True)
        )
        psu_count = psu_listings.scalar() or 0

        rows.append({
            'component_type': 'Power Supply',
            'manufacturer': '[Not tracked]',
            'model': '[Included in build]',
            'variant': '',
            'spec_detail': '',
            'listing_count': psu_count,
            'notes': 'Stored as boolean flag only (has_psu) - no model/wattage information tracked'
        })

        # =====================================================================
        # WRITE COMPREHENSIVE CSV
        # =====================================================================
        csv_path = Path('flipflop-all-components.csv')
        fieldnames = ['component_type', 'manufacturer', 'model', 'variant', 'spec_detail',
                      'listing_count', 'notes']

        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        # =====================================================================
        # PRINT SUMMARY
        # =====================================================================
        print(f"\n[RESULTS] Component Summary")
        print(f"  Total rows in CSV: {len(rows)}")
        print(f"  Output: {csv_path.resolve()}\n")

        # Group summary
        by_type = {}
        for row in rows:
            ct = row['component_type']
            if ct not in by_type:
                by_type[ct] = 0
            by_type[ct] += row['listing_count']

        print("[BREAKDOWN] Listings by Component Type:")
        print(f"  {'Type':<20} {'Count':>10} {'Distinct Models':<20}")
        print(f"  {'-'*52}")

        for ctype in sorted(by_type.keys()):
            count = by_type[ctype]
            models = len([r for r in rows if r['component_type'] == ctype])
            print(f"  {ctype:<20} {count:>10} {models:<20}")

        # =====================================================================
        # EXPLANATION
        # =====================================================================
        print(f"\n[EXPLANATION] Why Different Component Types Have Different Data:")
        print(f"""
RAM & STORAGE - NO DISTINCT MODELS:
  - Stored as NUMERIC CAPACITY ONLY (ram_gb, storage_gb as Integer)
  - Example: ram_gb=16 means 16GB, not "Corsair Vengeance Pro RGB 16GB DDR5"
  - Solution: Would need to parse individual product titles or maintain separate parts catalogue

PC CASES - NO STRUCTURED DATA:
  - Not tracked as a structured field in Listing model
  - No dedicated case field (unlike CPU, GPU, RAM_GB)
  - Case information exists ONLY in listing title text
  - Example: "Intel i7 build in NZXT H510 case" - case name is buried in title
  - Would require text parsing/NLP to extract distinct case models

PSU (Power Supply) - ONLY BOOLEAN:
  - Tracked as has_psu=True/False flag ONLY
  - No wattage, brand, or model information
  - {psu_count} listings have PSU included, but we don't know which models

CPU & GPU - FULL MODEL DATA:
  - Stored as string model names (Listing.cpu, Listing.gpu)
  - Already extracted/distinct from titles
  - Have {len([r for r in rows if r['component_type'] == 'CPU'])} CPU models
  - Have {len([r for r in rows if r['component_type'] == 'GPU'])} GPU models
        """)

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(extract_all_components())
