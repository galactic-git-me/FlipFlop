#!/usr/bin/env python3
"""
Verify that 3D models have been successfully integrated into the database.
"""

import sys
import asyncio
from pathlib import Path
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import AsyncSessionLocal
from app.models.case import Case


async def verify_integration():
    """Query the database to verify 3D model integration."""
    print("\n" + "="*80)
    print("VERIFYING 3D MODEL DATABASE INTEGRATION")
    print("="*80 + "\n")

    async with AsyncSessionLocal() as session:
        # Query cases with 3D models
        query = select(
            Case.id,
            Case.name,
            Case.model_3d_url,
            Case.model_3d_creator,
            Case.model_3d_license,
            Case.model_3d_quality,
            Case.model_3d_vertices,
            Case.model_3d_polygons,
            Case.model_3d_file_size,
        ).where(Case.has_3d_model == True).order_by(Case.id)

        result = await session.execute(query)
        cases = result.fetchall()

        if not cases:
            print("✗ NO 3D MODELS FOUND IN DATABASE\n")
            return False

        print(f"✓ FOUND {len(cases)} CASES WITH 3D MODELS\n")

        # Target case IDs
        target_ids = [559, 619, 659]
        found_ids = set()

        for row in cases:
            case_id, name, url, creator, license, quality, vertices, polygons, file_size = row

            if case_id in target_ids:
                found_ids.add(case_id)
                print(f"[ID: {case_id}] {name}")
                print(f"  URL: {url}")
                print(f"  Creator: {creator}")
                print(f"  License: {license}")
                print(f"  Quality: {quality}")
                print(f"  Vertices: {vertices:,}")
                print(f"  Polygons: {polygons:,}")
                size_mb = file_size / (1024*1024)
                print(f"  File Size: {file_size:,} bytes ({size_mb:.2f} MB)")
                print()

        # Summary
        print("="*80)
        print("VERIFICATION SUMMARY")
        print("="*80)
        print(f"Target cases: {len(target_ids)}")
        print(f"Found: {len(found_ids)}")
        print(f"Missing: {len(target_ids) - len(found_ids)}")

        if len(found_ids) == len(target_ids):
            print("\n✓ ALL 3 MODELS SUCCESSFULLY INTEGRATED")
            return True
        else:
            missing = target_ids - found_ids
            print(f"\n✗ MISSING CASE IDs: {sorted(missing)}")
            return False


if __name__ == "__main__":
    try:
        success = asyncio.run(verify_integration())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
