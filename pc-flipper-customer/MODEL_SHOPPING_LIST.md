# FlipFlop 3D Model Shopping List

Quick reference for downloading models from Sketchfab.

## What You Need (14 Total Models)

Total estimated download time: 20-40 minutes

### GPU (3 models)
- [ ] **Variant 1 (High-end):** RTX 4090 or nvidia high-end
- [ ] **Variant 2 (Mid):** GTX or mid-range graphics card
- [ ] **Variant 3 (Budget):** Basic graphics card or older GPU

Save as:
- `public/models/gpu/variant-1.gltf`
- `public/models/gpu/variant-2.gltf`
- `public/models/gpu/variant-3.gltf`

### CPU (3 models)
- [ ] **Variant 1 (High-end):** Intel i9 or high-end processor
- [ ] **Variant 2 (Mid):** Intel i7 or Ryzen 7
- [ ] **Variant 3 (Budget):** Basic CPU or budget processor

Save as:
- `public/models/cpu/variant-1.gltf`
- `public/models/cpu/variant-2.gltf`
- `public/models/cpu/variant-3.gltf`

### RAM (3 models)
- [ ] **Variant 1 (High-end):** DDR5 RGB or high-end memory
- [ ] **Variant 2 (Mid):** DDR4 standard memory
- [ ] **Variant 3 (Budget):** DDR3 or budget memory

Save as:
- `public/models/ram/variant-1.gltf`
- `public/models/ram/variant-2.gltf`
- `public/models/ram/variant-3.gltf`

### Storage (3 models)
- [ ] **Variant 1 (Fast):** NVMe M.2 SSD
- [ ] **Variant 2 (Mid):** 2.5" SSD
- [ ] **Variant 3 (Slow):** 3.5" HDD

Save as:
- `public/models/storage/variant-1.gltf`
- `public/models/storage/variant-2.gltf`
- `public/models/storage/variant-3.gltf`

### Cooling (2 models)
- [ ] **Variant 1 (Air):** Tower air cooler or noctua
- [ ] **Variant 2 (Liquid):** Liquid AIO cooler or water cooler

Save as:
- `public/models/cooling/variant-1.gltf`
- `public/models/cooling/variant-2.gltf`

## Download Steps

### For Each Model:

1. **Visit Sketchfab:** https://sketchfab.com

2. **Search** for the model name

3. **Filter:**
   - License: CC0 or CC-BY
   - Downloadable: Yes

4. **Download:**
   - Choose glTF or GLB format
   - (GLB is simpler - bundles textures)

5. **Extract** the ZIP file

6. **Place** the `.gltf` or `.glb` file:
   - Rename to `variant-{N}.gltf`
   - Move to `public/models/{type}/variant-{N}.gltf`

7. **If using glTF with textures:**
   - Also copy texture files to same directory
   - Or convert to GLB format (recommended)

## Verify Setup

```bash
# Check what you have so far
python3 download-models.py

# When all done, test in browser
npm run dev -- --port 3001
# Visit: http://andromeda-ts:3001/configure/gaming-rig
```

## Pro Tips

- **Use GLB format when available** - it's simpler (one file instead of many)
- **Check file size** - keep models under 10MB each
- **Test in browser** - use DevTools (F12) to check for errors
- **Pick popular models** - they tend to have better quality
- **Read the license** - make sure it's CC0 or CC-BY

## Common Issues

### Model doesn't show in configurator
```bash
# Check the file exists
ls -la public/models/gpu/variant-1.gltf

# Check browser console (F12) for error messages
```

### Textures appear white/broken
- Download as GLB format instead of glTF
- Or ensure all texture files are in the same directory

### Download too slow
- Choose a simpler model (fewer polygons)
- Look for GLB format (often smaller than glTF + textures)

## File Structure When Done

```
pc-flipper-customer/
└── public/models/
    ├── gpu/
    │   ├── variant-1.gltf
    │   ├── variant-2.gltf
    │   └── variant-3.gltf
    ├── cpu/
    │   ├── variant-1.gltf
    │   ├── variant-2.gltf
    │   └── variant-3.gltf
    ├── ram/
    │   ├── variant-1.gltf
    │   ├── variant-2.gltf
    │   └── variant-3.gltf
    ├── storage/
    │   ├── variant-1.gltf
    │   ├── variant-2.gltf
    │   └── variant-3.gltf
    └── cooling/
        ├── variant-1.gltf
        └── variant-2.gltf
```

## Questions?

See `MODEL_SOURCING_GUIDE.md` for detailed instructions and troubleshooting.
