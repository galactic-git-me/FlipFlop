# Automated Sketchfab Model Downloader

Automatically downloads all 19-21 3D models from Sketchfab for your high-end RGB gaming build.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements-download.txt

# 2. Install Playwright browsers
playwright install chromium

# 3. Run downloader (30-45 minutes, first run)
python3 download-models-auto.py
```

## What It Does

- Searches Sketchfab for each model using the curated search prompts
- Filters by CC0/CC-BY license and downloadable status
- Downloads glTF/GLB files automatically
- Extracts ZIPs automatically
- Organizes files into `public/models/{type}/variant-{N}.gltf`
- Skips already-downloaded models
- Respects rate limits (3s delay between downloads)

## Models Downloaded (16 total)

**GPU (3)**: RTX 4090, RTX 4080, RTX 3090 Ti  
**CPU (3)**: i9 + tower cooler, Ryzen 9 + AIO, CPU + RGB cooler  
**RAM (3)**: DDR5 RGB variants (Corsair, Kingston, Crucial)  
**Storage (3)**: NVMe RGB, 2.5" SSD RGB, high-cap NVMe  
**Cases (4)**: Black aquarium, white aquarium, Lian Li Dark Mirror, NZXT H510  

## Progress Tracking

Watch the console for real-time download progress:

```
GPU
============================================================
Searching: gpu/1 (RTX 4090)
  Downloaded: model.zip
✓ Extracted and saved: variant-1.gltf
Searching: gpu/2 (RTX 4080)
  Downloaded: model.glb
✓ Saved: variant-2.glb
...
============================================================
Download complete: 16/16 models
```

## Estimated Time

- **First run:** 30-45 minutes (all models)
- **Re-runs:** 2-5 minutes (skips existing files)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **"Playwright not installed"** | Run: `pip install -r requirements-download.txt` |
| **"chromium not found"** | Run: `playwright install chromium` |
| **No search results** | Try manual download with HIGH_END_GAMING_BUILD_SHOPPING_LIST.md |
| **"No download button"** | Model may require authentication; use manual fallback |
| **Rate limited** | Script waits 3s between downloads; increase delay if needed |

## Manual Fallback

If automation fails for a specific model:

1. Open [Sketchfab](https://sketchfab.com/search)
2. Use search prompts from `HIGH_END_GAMING_BUILD_SHOPPING_LIST.md`
3. Download glTF or GLB version
4. Extract to `public/models/{type}/variant-{N}.gltf`

## Next Steps

After download completes:

```bash
npm run dev -- --port 3001
# Visit http://andromeda-ts:3001/configure/gaming-rig
```

All your high-end RGB models will be loaded in the 3D configurator! 🎮
