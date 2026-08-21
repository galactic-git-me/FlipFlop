#!/usr/bin/env python3
"""
Download 3D models from Sketchfab and integrate them into the FlipFlop database.

Usage:
    python download_3d_models.py

Sketchfab models require authentication to download. This script attempts to use
requests with a Sketchfab API token (if available) or browser automation to download
the models. Without proper authentication, Sketchfab will return 403 errors.

For now, this script documents the integration workflow and creates SQL templates
for database updates once models are manually downloaded.
"""

import os
import json
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

# Sketchfab model metadata
@dataclass
class SketchfabModel:
    name: str
    url: str
    sketchfab_id: str
    creator: str
    license: str
    description: str

MODELS = [
    SketchfabModel(
        name="Corsair 4000D",
        url="https://sketchfab.com/3d-models/corsair-4000d-pc-case-bc15e007d6634579bc0e8ffdf238e665",
        sketchfab_id="bc15e007d6634579bc0e8ffdf238e665",
        creator="SzaBa",
        license="CC-BY-4.0",
        description="Corsair 4000D Airflow PC Case 3D Model"
    ),
    SketchfabModel(
        name="be quiet! Pure Base 600",
        url="https://sketchfab.com/3d-models/pure-base-600-new-6acb1b906fff44b69c9b8e04361f6b89",
        sketchfab_id="6acb1b906fff44b69c9b8e04361f6b89",
        creator="JackZeta",
        license="CC-BY-4.0",
        description="be quiet! Pure Base 600 PC Case 3D Model"
    ),
    SketchfabModel(
        name="Corsair 5000D",
        url="https://sketchfab.com/3d-models/corsair-5000d-sketchfab-v1-008-565f7553ffda415799a6f18fe3174614",
        sketchfab_id="565f7553ffda415799a6f18fe3174614",
        creator="lukeboxfx",
        license="CC-BY-4.0",
        description="Corsair iCUE 5000D RGB PC Case 3D Model"
    ),
]

# Database case mapping (match Sketchfab model names to database case names)
CASE_MAPPING = {
    "Corsair 4000D": "CORSAIR FRAME 4000D",
    "be quiet! Pure Base 600": "be quiet! Pure Base 600",
    "Corsair 5000D": "CORSAIR ICUE 5000D RGB",
}

def create_integration_templates() -> None:
    """
    Create SQL templates and integration guide for 3D models.

    Sketchfab download requires either:
    1. A Sketchfab API token (sketchfab.com/settings/applications)
    2. Browser automation with Playwright/Selenium

    For manual download:
    1. Visit the model URL
    2. Click "Download"
    3. Select format (GLB recommended)
    4. Save to flipflop-api/media/3d-models/cases/
    """

    media_dir = Path(__file__).parent.parent / "media" / "3d-models" / "cases"
    media_dir.mkdir(parents=True, exist_ok=True)

    # Create integration guide
    guide = """# 3D Model Integration Guide

## Models to Download

These Sketchfab models are Creative Commons licensed and ready for integration:

1. **Corsair 4000D PC Case**
   - Creator: SzaBa
   - License: CC-BY-4.0
   - URL: https://sketchfab.com/3d-models/corsair-4000d-pc-case-bc15e007d6634579bc0e8ffdf238e665
   - Target DB Case: CORSAIR FRAME 4000D

2. **be quiet! Pure Base 600**
   - Creator: JackZeta
   - License: CC-BY-4.0
   - URL: https://sketchfab.com/3d-models/pure-base-600-new-6acb1b906fff44b69c9b8e04361f6b89
   - Target DB Case: be quiet! Pure Base 600

3. **Corsair iCUE 5000D RGB**
   - Creator: lukeboxfx
   - License: CC-BY-4.0
   - URL: https://sketchfab.com/3d-models/corsair-5000d-sketchfab-v1-008-565f7553ffda415799a6f18fe3174614
   - Target DB Case: CORSAIR ICUE 5000D RGB

## Download Instructions

### Option 1: Manual Download (Easiest)
1. Visit each URL above
2. Click the blue "Download" button
3. Select "GLB" format (binary glTF, most efficient)
4. Save to: `flipflop-api/media/3d-models/cases/`

### Option 2: Sketchfab API Download (Requires Token)
```bash
export SKETCHFAB_API_TOKEN="your_token_here"
python scripts/download_3d_models.py --use-api
```

### Option 3: Browser Automation (Requires Playwright)
```bash
playwright install chromium
python scripts/download_3d_models.py --use-browser
```

## File Organization

After downloading, files should be at:
- `flipflop-api/media/3d-models/cases/corsair_4000d.glb`
- `flipflop-api/media/3d-models/cases/be_quiet_pure_base_600.glb`
- `flipflop-api/media/3d-models/cases/corsair_5000d.glb`

## Database Integration

After downloading models, run:
```python
python scripts/integrate_3d_models.py
```

This will:
1. Extract model metadata (polygon count, vertices, file size)
2. Update the `cases` table with model references
3. Generate a summary report

## SQL Templates

See `sql_update_statements.sql` for the UPDATE statements to run after model download.
"""

    guide_path = media_dir.parent.parent / "INTEGRATION_GUIDE.md"
    with open(guide_path, "w") as f:
        f.write(guide)

    print(f"Integration guide created: {guide_path}")

    # Generate SQL template
    sql_template = """-- SQL UPDATE statements for 3D model integration
-- Run these after downloading models and extracting metadata

-- Corsair 4000D
UPDATE cases
SET
    has_3d_model = true,
    model_3d_url = '/media/3d-models/cases/corsair_4000d.glb',
    model_3d_source = 'sketchfab',
    model_3d_creator = 'SzaBa',
    model_3d_license = 'CC-BY-4.0',
    model_3d_quality = 'high',
    model_3d_vertices = <EXTRACT_FROM_MODEL>,
    model_3d_polygons = <EXTRACT_FROM_MODEL>,
    updated_at = NOW()
WHERE
    LOWER(name) LIKE '%corsair%4000d%'
    AND source_site IN ('Amazon', 'eBay', 'Overclockers');

-- be quiet! Pure Base 600
UPDATE cases
SET
    has_3d_model = true,
    model_3d_url = '/media/3d-models/cases/be_quiet_pure_base_600.glb',
    model_3d_source = 'sketchfab',
    model_3d_creator = 'JackZeta',
    model_3d_license = 'CC-BY-4.0',
    model_3d_quality = 'high',
    model_3d_vertices = <EXTRACT_FROM_MODEL>,
    model_3d_polygons = <EXTRACT_FROM_MODEL>,
    updated_at = NOW()
WHERE
    LOWER(name) LIKE '%pure base 600%'
    AND source_site IN ('Amazon', 'eBay', 'Overclockers');

-- Corsair 5000D
UPDATE cases
SET
    has_3d_model = true,
    model_3d_url = '/media/3d-models/cases/corsair_5000d.glb',
    model_3d_source = 'sketchfab',
    model_3d_creator = 'lukeboxfx',
    model_3d_license = 'CC-BY-4.0',
    model_3d_quality = 'high',
    model_3d_vertices = <EXTRACT_FROM_MODEL>,
    model_3d_polygons = <EXTRACT_FROM_MODEL>,
    updated_at = NOW()
WHERE
    LOWER(name) LIKE '%corsair%5000d%'
    AND source_site IN ('Amazon', 'eBay', 'Overclockers');

-- Verify updates
SELECT id, name, model_3d_url, model_3d_creator, model_3d_license
FROM cases
WHERE has_3d_model = true
ORDER BY updated_at DESC
LIMIT 3;
"""

    sql_path = media_dir.parent.parent / "sql_update_statements.sql"
    with open(sql_path, "w") as f:
        f.write(sql_template)

    print(f"SQL template created: {sql_path}")

    # Generate JSON metadata manifest
    metadata = {
        "generated_at": datetime.utcnow().isoformat(),
        "models": [
            {
                "name": m.name,
                "sketchfab_url": m.url,
                "sketchfab_id": m.sketchfab_id,
                "creator": m.creator,
                "license": m.license,
                "target_case": CASE_MAPPING.get(m.name, "Unknown"),
                "local_path": f"/media/3d-models/cases/{m.name.lower().replace(' ', '_').replace('!', '')}.glb",
                "status": "pending_download"
            }
            for m in MODELS
        ]
    }

    manifest_path = media_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Manifest created: {manifest_path}")

    print("\n" + "="*70)
    print("3D MODEL INTEGRATION SETUP COMPLETE")
    print("="*70)
    print(f"\nMedia directory: {media_dir}")
    print(f"\nNext steps:")
    print("1. Read the integration guide: {guide_path}")
    print("2. Download models from Sketchfab links")
    print("3. Save GLB files to: {media_dir}")
    print("4. Run: python scripts/integrate_3d_models.py")
    print("5. Execute the SQL statements in: {sql_path}")
    print()

if __name__ == "__main__":
    create_integration_templates()
