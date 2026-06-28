# FlipFlop 3D Model Sourcing Guide

This guide walks you through finding, downloading, and organizing 3D models from Sketchfab for the FlipFlop PC configurator.

## Quick Start

```bash
# Generate the model structure and see what's needed
python3 download-models.py
```

This will:
1. Create the `public/models/` directory structure
2. Show you the shopping list
3. Display which models you already have
4. Provide testing instructions

## Directory Structure

```
pc-flipper-customer/
└── public/models/
    ├── gpu/
    │   ├── variant-1.gltf  (RTX 4090 / High-end)
    │   ├── variant-2.gltf  (GTX Mid / Mid-range)
    │   └── variant-3.gltf  (Budget GPU)
    ├── cpu/
    │   ├── variant-1.gltf  (Intel i9 / High-end)
    │   ├── variant-2.gltf  (i7/Ryzen 7 / Mid-range)
    │   └── variant-3.gltf  (Budget CPU)
    ├── ram/
    │   ├── variant-1.gltf  (DDR5 RGB / High-end)
    │   ├── variant-2.gltf  (DDR4 / Mid-range)
    │   └── variant-3.gltf  (DDR3 / Budget)
    ├── storage/
    │   ├── variant-1.gltf  (NVMe M.2 / Fast)
    │   ├── variant-2.gltf  (2.5" SSD / Mid)
    │   └── variant-3.gltf  (3.5" HDD / Slow)
    └── cooling/
        ├── variant-1.gltf  (Tower Air Cooler / High-end)
        └── variant-2.gltf  (Liquid AIO / Modern)
```

## Downloading from Sketchfab

### Step 1: Visit Sketchfab

Go to https://sketchfab.com

### Step 2: Search and Filter

Use filters to find CC-licensed, downloadable models:
- **License:** CC0 or CC-BY
- **Downloadable:** Yes
- **Sort by:** Most popular or newest

### Step 3: Download the Model

1. Click on a model you like
2. Scroll down to "Downloads" section
3. Look for "glTF" or "GLB" format (not FBX or OBJ)
4. Click the download button
5. Save the ZIP file

### Step 4: Extract and Place

1. Extract the downloaded ZIP file
2. Look for `.gltf` or `.glb` file (the 3D model file)
3. Rename it to match the variant number:
   - For GPU variant 1: rename to `variant-1.gltf`
   - For CPU variant 2: rename to `variant-2.gltf`
   - etc.
4. Move it to the appropriate directory:
   - `public/models/gpu/variant-1.gltf`
   - `public/models/cpu/variant-2.gltf`
   - etc.

### Step 5: Handle Texture Files (Important!)

If the downloaded folder contains texture files (`.png`, `.jpg`, etc.):

**Option A: Keep textures with the model (Recommended)**
```
public/models/gpu/
├── variant-1.gltf
├── variant-1.bin
└── textures/
    ├── texture_1.png
    ├── texture_2.jpg
    └── ...
```

The `.gltf` file references these textures, so they must be in the same directory structure.

**Option B: Use GLB format (Self-contained)**
Some Sketchfab models offer `.glb` format (binary glTF with embedded textures):
```
public/models/gpu/variant-1.glb
```

Choose GLB if available - it's simpler since everything is in one file.

## Model Search Terms

### GPU Components
- **High-end:** "RTX 4090", "nvidia graphics card", "gpu high end"
- **Mid-range:** "GTX 1080", "graphics card mid", "gpu"
- **Budget:** "graphics card", "old graphics card", "budget gpu"

### CPU Components
- **High-end:** "Intel i9", "cpu cooler tower", "processor high end"
- **Mid-range:** "Intel i7", "Ryzen 7", "processor"
- **Budget:** "cpu", "processor", "budget cpu"

### RAM Components
- **High-end:** "DDR5 RAM", "memory RGB", "ddr5"
- **Mid-range:** "DDR4", "memory stick", "ddr4"
- **Budget:** "DDR3", "memory", "ddr3"

### Storage Components
- **Fast:** "NVMe", "M.2 SSD", "nvme ssd"
- **Mid:** "2.5 SSD", "laptop ssd", "2.5 inch ssd"
- **Slow:** "hard drive", "HDD", "3.5 hard drive"

### Cooling Components
- **High-end:** "CPU cooler", "noctua", "air cooler tower"
- **Modern:** "liquid cooler", "AIO cooler", "water cooler"

## Verifying Your Models

After placing models, verify they load correctly:

```bash
# Check which models you have
python3 download-models.py

# Start the dev server
npm run dev -- --port 3001

# Open the configurator
# Visit: http://andromeda-ts:3001/configure/gaming-rig

# Test:
# 1. Hover over components - you should see labels
# 2. Click a component - modal should open showing your models
# 3. Select different tiers - models should change
# 4. Open browser console (F12) - no red errors about models
```

## Troubleshooting

### Model doesn't show up in the configurator

**Check file path:**
```bash
ls -la public/models/gpu/
# Should show: variant-1.gltf, variant-2.gltf, variant-3.gltf
```

**Check browser console:**
1. Open DevTools (F12)
2. Go to Console tab
3. Look for errors like "Failed to load model"
4. Verify the error message shows the expected file path

### Textures not showing (model appears white/blank)

**If using `.gltf` with separate texture files:**
1. Ensure texture files are in the same directory as the `.gltf` file
2. The `.gltf` file references textures by filename - they must exist
3. Check the `.gltf` file (it's text) - look for `"uri": "..."`
4. Make sure filenames match exactly (case-sensitive)

**Solution: Use `.glb` instead**
- Download as GLB format if available (bundles textures)
- Place `.glb` file as `public/models/gpu/variant-1.glb`
- No need to manage separate texture files

### Download fails or model is too large

**Model size guidelines:**
- Ideal: < 5MB per model
- Acceptable: < 10MB per model
- Too large: > 20MB (slow to load)

If model is too large, try a simpler model from Sketchfab search.

## Example: Complete Workflow

```bash
# 1. Generate the directory structure
python3 download-models.py

# 2. Visit Sketchfab and download models
# Example: RTX_4090.zip

# 3. Extract
unzip RTX_4090.zip

# 4. Copy to correct location
cp scene.gltf public/models/gpu/variant-1.gltf
cp scene.bin public/models/gpu/

# 5. If using glTF with textures
cp -r textures/ public/models/gpu/

# 6. Verify in browser
npm run dev -- --port 3001
# Open: http://andromeda-ts:3001/configure/gaming-rig

# 7. Repeat for other components

# 8. Final check
python3 download-models.py
```

## File Format Details

### GLTF (.gltf)
- Text-based format
- References textures as separate files
- Requires texture files to be in correct location
- Good for debugging

### GLB (.glb)
- Binary format
- Bundles textures into single file
- Recommended if available
- Simpler to manage

**Recommendation:** Use GLB when available, fall back to glTF with textures otherwise.
