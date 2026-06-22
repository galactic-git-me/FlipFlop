# Automated Sketchfab Model Downloader

Automatically downloads all 19-21 3D models from Sketchfab for your high-end RGB gaming build.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements-download.txt

# 2. Install Playwright browsers
playwright install chromium

# 3. Run downloader
python3 download-models-auto.py
```

The script will:
- Search Sketchfab for each model using curated search prompts
- Filter by CC0/CC-BY license
- Download glTF/GLB files
- Extract ZIPs automatically
- Organize files into `public/models/{type}/variant-{N}.gltf`
- Skip already-downloaded models
- Show real-time progress

## What Gets Downloaded

| Component | Variants | Files |
|-----------|----------|-------|
| GPU       | 3        | gpu/variant-{1-3}.gltf |
| CPU       | 3        | cpu/variant-{1-3}.gltf |
| RAM       | 3        | ram/variant-{1-3}.gltf |
| Storage   | 3        | storage/variant-{1-3}.gltf |
| Cases     | 4        | cases/variant-{1-4}.gltf |
| **Total** | **16**   | **16 models** |

## How It Works

1. **Browser Automation**: Uses Playwright to control a headless Chromium browser
2. **Search**: For each model, searches Sketchfab using exact prompts from `HIGH_END_GAMING_BUILD_SHOPPING_LIST.md`
3. **Filter**: Automatically filters by CC0/CC-BY license and downloadable status
4. **Download**: Clicks the download button and captures the file
5. **Extract**: If the file is a ZIP, automatically extracts the glTF/GLB model
6. **Organize**: Saves to the correct directory in `public/models/`
7. **Rate Limit**: Waits 3 seconds between searches to be respectful to Sketchfab

## Progress Output

Watch the console for real-time progress:

```
Starting download of 16 models...
======================================================================

GPU
----------------------------------------------------------------------
Searching: gpu/1 (RTX 4090)
  Search term: RTX 4090 OR "nvidia RTX 4090" OR...
  Found model: https://sketchfab.com/3d-models/...
  Downloaded: model.zip
✓ Extracted and saved: variant-1.gltf

Searching: gpu/2 (RTX 4080)
  Search term: RTX 4080 OR RTX 4070 Ti OR...
  Found model: https://sketchfab.com/3d-models/...
  Downloaded: model.glb
✓ Saved: variant-2.glb

...

======================================================================
Download complete!
======================================================================
Successfully downloaded: 16/16 models
Models saved to: public/models/

Next steps:
  1. npm install (if needed)
  2. npm run dev -- --port 3001
  3. Visit http://andromeda-ts:3001/configure/gaming-rig
```

## Estimated Time

- **First run**: 30-45 minutes (all 16 models)
- **Re-runs**: 2-5 minutes (skips existing files)
- **Per model**: 2-3 minutes average (depends on Sketchfab load)

## Requirements

- Python 3.7+
- pip (Python package manager)
- Internet connection
- ~2GB free disk space (temporary)

## Troubleshooting

### Playwright not installed
```bash
pip install -r requirements-download.txt
```

### Browsers not installed
```bash
playwright install chromium
```

### Script gets "Connection refused"
- Check your internet connection
- Sketchfab may be temporarily down
- Try again in a few minutes

### Some models fail to download
- This is normal — Sketchfab availability varies
- The script will skip already-downloaded models on re-run
- Failed models: check the console log for specific errors

### Script is too slow
- This is intentional (3 second delay between searches)
- Sketchfab has rate limits; going faster causes blocks
- You can modify `await asyncio.sleep(3)` in the script if needed

### Wrong model gets downloaded
- Search terms may find different results based on Sketchfab's algorithm
- If a specific model needs to be replaced:
  1. Manually download from `HIGH_END_GAMING_BUILD_SHOPPING_LIST.md`
  2. Place in `public/models/{type}/variant-{N}.gltf`
  3. Script will skip it on re-run

## Manual Fallback

If automation fails for a specific model:

1. Open `HIGH_END_GAMING_BUILD_SHOPPING_LIST.md`
2. Find the component you need
3. Copy the "Sketchfab Search Prompt"
4. Go to https://sketchfab.com/search
5. Paste the search term
6. Filter: License (CC0 or CC-BY) + Downloadable (Yes)
7. Click first result
8. Download glTF or GLB
9. Extract if ZIP
10. Place in `public/models/{type}/variant-{N}.gltf`

## After Download

Once all models are downloaded:

```bash
# Start the dev server
npm run dev -- --port 3001

# Open your browser
# Visit: http://andromeda-ts:3001/configure/gaming-rig
```

You'll see your high-end RGB gaming build in full 3D! All models will be interactive and rotatable.

## File Sizes

Models are organized by size to optimize loading:

| Type | Typical Size | Count |
|------|--------------|-------|
| CPU | 500KB-2MB | 3 |
| GPU | 300-1000KB | 3 |
| RAM | 100-400KB | 3 |
| Storage | 80-250KB | 3 |
| Cases | 1-3.5MB | 4 |

Total: ~15-20MB for all models

## Advanced Options

### Show browser window (for debugging)

Edit `download-models-auto.py` and change:
```python
browser = await p.chromium.launch(headless=True)
```
to:
```python
browser = await p.chromium.launch(headless=False)
```

Then you can see what the script is doing.

### Change rate limit

Edit `download-models-auto.py` and find:
```python
await asyncio.sleep(3)
```

Change `3` to a different number (in seconds).

### Add more models

Edit the `MODELS_CONFIG` dictionary in `download-models-auto.py` to add more components or variants.

## Support

If models fail to download:

1. Check `HIGH_END_GAMING_BUILD_SHOPPING_LIST.md` for manual search terms
2. Search Sketchfab manually if the script struggles
3. Look for models with CC0 or CC-BY license
4. Prefer glTF/GLB format
5. Make sure "Downloadable" is selected

All your high-end RGB models will be ready to configure!
