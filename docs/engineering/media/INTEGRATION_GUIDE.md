# 3D Model Integration Guide

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
