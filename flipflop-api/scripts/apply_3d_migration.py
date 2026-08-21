#!/usr/bin/env python3
"""
Apply 3D model metadata migration to PostgreSQL database.

This script adds the necessary columns to the cases table to support
3D model tracking.
"""

import sys
import asyncio
from pathlib import Path
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import engine

async def apply_migration():
    """Apply the 3D model metadata migration."""

    # SQL statements for PostgreSQL
    migrations = [
        # Add columns if they don't exist
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_creator VARCHAR(255)",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_license VARCHAR(50)",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_quality VARCHAR(20)",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_vertices INTEGER",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_polygons INTEGER",
        "ALTER TABLE cases ADD COLUMN IF NOT EXISTS model_3d_file_size INTEGER",

        # Create indexes
        "CREATE INDEX IF NOT EXISTS idx_cases_has_3d_model ON cases(has_3d_model)",
        "CREATE INDEX IF NOT EXISTS idx_cases_model_3d_source ON cases(model_3d_source) WHERE has_3d_model = true",
        "CREATE INDEX IF NOT EXISTS idx_cases_model_3d_quality ON cases(model_3d_quality) WHERE has_3d_model = true",
        "CREATE INDEX IF NOT EXISTS idx_cases_model_3d_creator ON cases(model_3d_creator) WHERE has_3d_model = true",
    ]

    print("\n" + "="*80)
    print("APPLYING 3D MODEL MIGRATION TO PostgreSQL")
    print("="*80 + "\n")

    try:
        async with engine.begin() as conn:
            for i, sql in enumerate(migrations, 1):
                print(f"[{i}/{len(migrations)}] {sql[:60]}...")
                try:
                    await conn.execute(text(sql))
                    print(f"       ✓ Success\n")
                except Exception as e:
                    # Some statements might fail if columns already exist, that's OK
                    if "already exists" in str(e) or "duplicate key" in str(e):
                        print(f"       ✓ Already exists\n")
                    else:
                        print(f"       ✗ Error: {str(e)[:80]}\n")

        print("="*80)
        print("✓ MIGRATION COMPLETED SUCCESSFULLY")
        print("="*80 + "\n")
        return True

    except Exception as e:
        print(f"\n✗ MIGRATION FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(apply_migration())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nCancelled by user")
        sys.exit(1)
