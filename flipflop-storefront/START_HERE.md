# FlipFlop 3D Models - START HERE

This guide helps you get real 3D models from Sketchfab into the FlipFlop PC configurator.

## What This Is

A Python script that:
- Creates the directory structure for 3D models
- Shows you what models you need (14 total)
- Provides search terms for Sketchfab
- Verifies your downloads are in place
- Shows how to test in the browser

## 30-Second Quick Start

```bash
# 1. Run the script
python3 download-models.py

# 2. Visit Sketchfab and download the models from the shopping list
https://sketchfab.com

# 3. Place downloaded files in public/models/{type}/variant-{N}.gltf

# 4. Run the script again to verify
python3 download-models.py

# 5. Test in browser
npm run dev -- --port 3001
# Open: http://andromeda-ts:3001/configure/gaming-rig
```

## What You Need

**14 models total** - takes about 20-40 minutes to download and place

| Component | High-end | Mid-range | Budget |
|-----------|----------|-----------|--------|
| **GPU** | RTX 4090 | GTX | Budget GPU |
| **CPU** | Intel i9 | i7/Ryzen 7 | Budget CPU |
| **RAM** | DDR5 RGB | DDR4 | DDR3 |
| **Storage** | NVMe M.2 | 2.5" SSD | 3.5" HDD |
| **Cooling** | Air Cooler | Liquid AIO | - |

## Files You Have

| File | Purpose |
|------|---------|
| `download-models.py` | Main script - run this to check status |
| `QUICK_START_MODELS.sh` | Shell wrapper (optional - same as above) |
| `MODEL_SHOPPING_LIST.md` | Quick checklist of what to download |
| `MODEL_SOURCING_GUIDE.md` | Detailed step-by-step instructions |
| `MODELS_SETUP_SUMMARY.txt` | Complete reference guide |
| `public/models/` | Directory structure for your models |

## Two Ways to Run

**Option A: Python (Recommended)**
```bash
python3 download-models.py
```

**Option B: Shell Wrapper**
```bash
bash QUICK_START_MODELS.sh
```

Both do the same thing. Choose whichever you prefer.

## What Happens When You Run It

The script:

1. **Creates directories** in `public/models/`
   - gpu/, cpu/, ram/, storage/, cooling/

2. **Shows shopping list**
   - Lists each model you need
   - Provides search terms for Sketchfab
   - Shows exactly where to place each file

3. **Checks existing models**
   - Lists which models are already placed
   - Shows file sizes and total storage

4. **Provides testing guide**
   - URL to open in browser
   - Steps to verify models work
   - Console debugging tips

## Step-by-Step Workflow

### Step 1: Run the Script
```bash
python3 download-models.py
```
Output shows what you need to download.

### Step 2: Visit Sketchfab
1. Go to https://sketchfab.com
2. Search for each model (e.g., "RTX 4090")
3. Filter: License = CC0 or CC-BY, Downloadable = Yes
4. Download glTF or GLB format
5. Extract the ZIP file

### Step 3: Place the Files
```
Downloaded: RTX_4090.zip
Extract and find: scene.gltf (or scene.glb)
Place in: public/models/gpu/variant-1.gltf
```

### Step 4: Verify
```bash
python3 download-models.py
# Should show all models you've placed
```

### Step 5: Test in Browser
```bash
npm run dev -- --port 3001
# Open: http://andromeda-ts:3001/configure/gaming-rig
# Click on components to see your models
```

## Search Terms Quick Reference

- **GPU:** "RTX 4090", "GTX", "graphics card"
- **CPU:** "Intel i9", "Intel i7", "Ryzen 7", "processor"
- **RAM:** "DDR5", "DDR4", "DDR3", "memory"
- **Storage:** "NVMe", "M.2 SSD", "2.5 SSD", "hard drive"
- **Cooling:** "CPU cooler", "liquid cooler", "AIO cooler"

## Pro Tips

1. **Use GLB format when available** - simpler (one file, includes textures)
2. **Keep models under 10MB** - loads faster
3. **Sort by popular** - usually better quality
4. **Check the preview** - make sure it looks good on Sketchfab

## Troubleshooting

**Model doesn't appear?**
- Check file exists: `ls -la public/models/gpu/variant-1.gltf`
- Open browser console (F12) and look for errors
- Verify the error shows the path you placed the file

**Textures appear white?**
- Use GLB format instead of glTF
- Or ensure all texture files are in the same directory as the .gltf file

**Download is slow?**
- Choose a simpler model (fewer polygons)
- Try GLB format (often smaller file size)

## File Structure When Done

```
public/models/
├── gpu/
│   ├── variant-1.gltf  (High-end GPU)
│   ├── variant-2.gltf  (Mid-range GPU)
│   └── variant-3.gltf  (Budget GPU)
├── cpu/
│   ├── variant-1.gltf  (High-end CPU)
│   ├── variant-2.gltf  (Mid-range CPU)
│   └── variant-3.gltf  (Budget CPU)
├── ram/
│   ├── variant-1.gltf  (High-end RAM)
│   ├── variant-2.gltf  (Mid-range RAM)
│   └── variant-3.gltf  (Budget RAM)
├── storage/
│   ├── variant-1.gltf  (Fast storage - NVMe)
│   ├── variant-2.gltf  (Mid storage - 2.5" SSD)
│   └── variant-3.gltf  (Slow storage - HDD)
└── cooling/
    ├── variant-1.gltf  (Air cooler)
    └── variant-2.gltf  (Liquid cooler)
```

## Need More Help?

- **Quick checklist:** See `MODEL_SHOPPING_LIST.md`
- **Detailed guide:** See `MODEL_SOURCING_GUIDE.md`
- **Complete reference:** See `MODELS_SETUP_SUMMARY.txt`

## Commands You'll Use

```bash
# Check what models you have
python3 download-models.py

# Start dev server
npm run dev -- --port 3001

# Test in browser
# Open: http://andromeda-ts:3001/configure/gaming-rig

# Verify a file exists
ls -la public/models/gpu/variant-1.gltf

# Check browser console for errors
# Press F12, go to Console tab
```

## Expected Timings

- **Running script:** < 1 second
- **Downloading all 14 models:** 20-40 minutes
- **Placing files:** 5-10 minutes
- **Testing:** 2-5 minutes

**Total: ~30-55 minutes**

## Next Steps

1. Run `python3 download-models.py` now
2. Read the shopping list it generates
3. Visit Sketchfab and start downloading models
4. Place them in the directories shown
5. Run the script again to verify
6. Test in browser

Good luck! The 3D configurator will look amazing with real PC component models.
