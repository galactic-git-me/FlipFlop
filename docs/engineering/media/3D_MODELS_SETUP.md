# 3D Models Integration Guide

## Overview

This guide explains how to download Creative Commons licensed 3D models from Sketchfab and integrate them into the FlipFlop database for PC cases.

## Models Available for Download

### 1. Corsair 4000D PC Case

- **Sketchfab URL**: https://sketchfab.com/3d-models/corsair-4000d-pc-case-bc15e007d6634579bc0e8ffdf238e665
- **Creator**: SzaBa
- **License**: CC-BY-4.0 (Requires attribution)
- **Target Database Case**: "CORSAIR FRAME 4000D"
- **Expected Filename**: `corsair_4000d.glb`
- **Approximate File Size**: 5-15 MB

### 2. be quiet! Pure Base 600

- **Sketchfab URL**: https://sketchfab.com/3d-models/pure-base-600-new-6acb1b906fff44b69c9b8e04361f6b89
- **Creator**: JackZeta
- **License**: CC-BY-4.0 (Requires attribution)
- **Target Database Case**: "be quiet! Pure Base 600"
- **Expected Filename**: `be_quiet_pure_base_600.glb`
- **Approximate File Size**: 5-15 MB

### 3. Corsair iCUE 5000D RGB

- **Sketchfab URL**: https://sketchfab.com/3d-models/corsair-5000d-sketchfab-v1-008-565f7553ffda415799a6f18fe3174614
- **Creator**: lukeboxfx
- **License**: CC-BY-4.0 (Requires attribution)
- **Target Database Case**: "CORSAIR ICUE 5000D RGB"
- **Expected Filename**: `corsair_5000d.glb`
- **Approximate File Size**: 5-15 MB

## Manual Download Instructions

### Step 1: Download from Sketchfab

For each model:

1. Click the model's Sketchfab URL above
2. Click the blue **"Download"** button (usually bottom-right)
3. A dropdown menu will appear with format options
4. Select **"GLB"** format (Binary glTF - most efficient and web-ready)
5. The download should start automatically

### Step 2: Save to Local Directory

Move or save each downloaded file to:
```
flipflop-api/media/3d-models/cases/
```

Expected file structure:
```
flipflop-api/
├── media/
│   └── 3d-models/
│       └── cases/
│           ├── corsair_4000d.glb
│           ├── be_quiet_pure_base_600.glb
│           ├── corsair_5000d.glb
│           └── manifest.json (auto-generated)
```

### Step 3: Verify File Integrity

After downloading, verify file sizes (should be 5-15 MB each):
```bash
cd flipflop-api/media/3d-models/cases/
ls -lh *.glb
```

All three files should exist and be non-zero size.

### Step 4: Run Integration Script

Once models are downloaded, run:
```bash
cd flipflop-api
python scripts/integrate_3d_models.py
```

This script will:
1. Extract model metadata (vertices, polygons, file size)
2. Estimate quality level (low/medium/high)
3. Update the `cases` table with model references
4. Generate `integration_report.json`

## Database Schema

The `cases` table includes the following new columns for 3D models:

```sql
-- 3D model status columns (already in schema)
has_3d_model BOOLEAN DEFAULT false         -- Whether model exists
model_3d_url VARCHAR(255)                   -- Local or CDN URL to GLB file
model_3d_source VARCHAR(50)                 -- Source: "sketchfab", "meshy_ai", etc.

-- 3D model metadata (NEW columns)
model_3d_creator VARCHAR(255)               -- Artist/creator name
model_3d_license VARCHAR(50)                -- License: "CC-BY-4.0", etc.
model_3d_quality VARCHAR(20)                -- "low", "medium", "high"
model_3d_vertices INTEGER                   -- Vertex count
model_3d_polygons INTEGER                   -- Polygon/triangle count
model_3d_file_size INTEGER                  -- File size in bytes
```

### SQL Migration

To add these columns to an existing PostgreSQL database:

```sql
ALTER TABLE cases ADD COLUMN model_3d_creator VARCHAR(255);
ALTER TABLE cases ADD COLUMN model_3d_license VARCHAR(50);
ALTER TABLE cases ADD COLUMN model_3d_quality VARCHAR(20);
ALTER TABLE cases ADD COLUMN model_3d_vertices INTEGER;
ALTER TABLE cases ADD COLUMN model_3d_polygons INTEGER;
ALTER TABLE cases ADD COLUMN model_3d_file_size INTEGER;

-- Create index for efficient queries
CREATE INDEX idx_cases_has_3d_model ON cases(has_3d_model);
```

## Expected SQL Updates

After running the integration script, the database will be updated with:

```sql
-- Corsair 4000D
UPDATE cases
SET
    has_3d_model = true,
    model_3d_url = '/media/3d-models/cases/corsair_4000d.glb',
    model_3d_source = 'sketchfab',
    model_3d_creator = 'SzaBa',
    model_3d_license = 'CC-BY-4.0',
    model_3d_quality = '<extracted>',
    model_3d_vertices = <extracted>,
    model_3d_polygons = <extracted>,
    model_3d_file_size = <extracted>
WHERE name ILIKE '%corsair 4000d%' OR name ILIKE '%corsair frame 4000d%';

-- be quiet! Pure Base 600
UPDATE cases
SET
    has_3d_model = true,
    model_3d_url = '/media/3d-models/cases/be_quiet_pure_base_600.glb',
    model_3d_source = 'sketchfab',
    model_3d_creator = 'JackZeta',
    model_3d_license = 'CC-BY-4.0',
    model_3d_quality = '<extracted>',
    model_3d_vertices = <extracted>,
    model_3d_polygons = <extracted>,
    model_3d_file_size = <extracted>
WHERE name ILIKE '%pure base 600%' OR name ILIKE '%be quiet%pure base%600%';

-- Corsair 5000D
UPDATE cases
SET
    has_3d_model = true,
    model_3d_url = '/media/3d-models/cases/corsair_5000d.glb',
    model_3d_source = 'sketchfab',
    model_3d_creator = 'lukeboxfx',
    model_3d_license = 'CC-BY-4.0',
    model_3d_quality = '<extracted>',
    model_3d_vertices = <extracted>,
    model_3d_polygons = <extracted>,
    model_3d_file_size = <extracted>
WHERE name ILIKE '%corsair%5000d%' OR name ILIKE '%corsair icue 5000d%';
```

## Verification Queries

After integration, verify models were added:

```sql
-- Check all cases with 3D models
SELECT 
    id, name, model_3d_url, model_3d_creator, model_3d_license,
    model_3d_quality, model_3d_vertices, model_3d_polygons
FROM cases
WHERE has_3d_model = true
ORDER BY updated_at DESC;

-- Count models by source
SELECT model_3d_source, COUNT(*) as count
FROM cases
WHERE has_3d_model = true
GROUP BY model_3d_source;

-- Find cases still pending model assignment
SELECT id, name, source_site
FROM cases
WHERE has_3d_model = false
ORDER BY bestseller_rank ASC
LIMIT 10;
```

## API Endpoints

Once integrated, 3D models are available through:

### Get Case with 3D Model
```
GET /api/cases/{case_id}

Response includes:
{
  "id": 123,
  "name": "CORSAIR FRAME 4000D",
  "has_3d_model": true,
  "model_3d_url": "/media/3d-models/cases/corsair_4000d.glb",
  "model_3d_source": "sketchfab",
  "model_3d_creator": "SzaBa",
  "model_3d_license": "CC-BY-4.0",
  "model_3d_quality": "high",
  "model_3d_vertices": 45000,
  "model_3d_polygons": 22500,
  ...
}
```

### List Cases with 3D Models
```
GET /api/cases?has_3d_model=true

Returns all cases with 3D models available
```

## Troubleshooting

### Issue: "Access Denied (403)" when downloading

**Solution**: Sketchfab may require authentication. Either:
1. Visit the URL manually and download using your browser
2. Create a Sketchfab account and add API token to environment
3. Use browser automation (Playwright) to automate download

### Issue: File download is slow or times out

**Solution**:
1. Check internet connection
2. Increase timeout in integration script
3. Download manually and place files in `media/3d-models/cases/`
4. Run integration script (it will detect existing files)

### Issue: GLB file is corrupted or invalid

**Solution**:
1. Delete the file and re-download
2. Verify file size matches expected range (5-15 MB)
3. Verify magic bytes: `xxd -l 12 filename.glb` should show `4c 54 66 00`

### Issue: Case name doesn't match database

**Solution**:
1. Query database to find exact case names:
   ```sql
   SELECT DISTINCT name FROM cases 
   WHERE source_site IN ('Amazon', 'eBay', 'Overclockers')
   AND name ILIKE '%corsair%';
   ```
2. Update the `CASE_MAPPING` in integration script
3. Re-run integration

## CDN Upload (Optional)

For production use, upload models to a CDN:

```bash
# Upload to your CDN (e.g., Cloudflare, AWS S3, etc.)
aws s3 cp flipflop-api/media/3d-models/cases/*.glb s3://your-bucket/3d-models/cases/

# Update model_3d_url in database to CDN paths
UPDATE cases
SET model_3d_url = 'https://cdn.example.com/3d-models/cases/' || split_part(model_3d_url, '/', -1)
WHERE has_3d_model = true AND model_3d_source = 'sketchfab';
```

## License Compliance

All models are CC-BY-4.0 licensed, which requires:

1. **Attribution**: Include creator name and license in product pages
2. **License Link**: Link to CC-BY-4.0 license
3. **Modification Notice**: If models are modified, document changes
4. **No Restrictions**: Can be used commercially and modified

Example attribution HTML:
```html
<div class="model-credit">
  <p>3D Model: Corsair 4000D</p>
  <p>Creator: <a href="https://sketchfab.com/SzaBa">SzaBa</a></p>
  <p>License: <a href="https://creativecommons.org/licenses/by/4.0/">CC-BY-4.0</a></p>
</div>
```

## Next Steps

1. Download all three GLB files from Sketchfab
2. Save to `flipflop-api/media/3d-models/cases/`
3. Run: `python scripts/integrate_3d_models.py`
4. Verify with: `python scripts/verify_3d_models.py`
5. Push changes to production
6. Update API documentation with 3D model endpoints
