# 3D Component Models

This directory contains glTF/GLB 3D models for PC components displayed in the 3D configurator.

## 📚 Full Sourcing Guide

See **`MODEL_SOURCING_GUIDE.md`** in the project root for comprehensive instructions on:
- Finding high-quality models on Sketchfab
- Recommended models by component type and performance tier
- Step-by-step integration process
- Performance optimization techniques
- Troubleshooting and FAQ

Quick link: `../MODEL_SOURCING_GUIDE.md`

## Quick Start

1. Visit https://sketchfab.com
2. Search for PC components (e.g., "RTX 4090", "CPU cooler")
3. Filter by **License**: CC0 or CC-BY (free to use)
4. Filter by **Downloadable**: Yes
5. Download in **glTF** or **GLB** format
6. Extract ZIP and copy `.gltf` files to appropriate folders below
7. Name as: `variant-1.gltf`, `variant-2.gltf`, `variant-3.gltf`
8. Run `npm run dev` and test in configurator

## Directory Structure

```
models/
├── gpu/
│   ├── variant-1.gltf    # High-end GPU (e.g., RTX 4090)
│   ├── variant-2.gltf    # Mid-range GPU (e.g., RTX 3070)
│   └── variant-3.gltf    # Budget GPU
├── cpu/
│   ├── variant-1.gltf    # High-end CPU (e.g., i9)
│   ├── variant-2.gltf    # Mid-range CPU (e.g., i7)
│   └── variant-3.gltf    # Budget CPU (e.g., i5)
├── ram/
│   ├── variant-1.gltf    # DDR5 (modern)
│   ├── variant-2.gltf    # DDR4/5 (standard)
│   └── variant-3.gltf    # DDR3 (legacy)
├── storage/
│   ├── variant-1.gltf    # M.2 NVMe (fastest)
│   ├── variant-2.gltf    # 2.5" SSD (medium)
│   └── variant-3.gltf    # 3.5" HDD (traditional)
└── cooling/
    ├── variant-1.gltf    # Air tower cooler
    └── variant-2.gltf    # Liquid AIO cooler
```

## Setup Helper Script

Run the setup script to check your directory structure:
```bash
bash DOWNLOAD_MODELS.sh
```

This will:
- Verify all component directories exist
- Show currently loaded models
- Provide step-by-step instructions

## Model Requirements

| Requirement | Specification |
|---|---|
| **Format** | glTF 2.0 (.gltf or .glb) |
| **Max Size** | 2MB (aim for 300-800KB) |
| **License** | CC0 or CC-BY (free commercial use) |
| **Scale** | ~1 unit = 1 inch |
| **Origin** | Centered at (0, 0, 0) |
| **Textures** | Embedded in .glb when possible |

## Recommended Component Models

### GPU (Graphics Cards)
- **High-end**: RTX 4090, RTX 4080, RX 7900 style
- **Mid-range**: RTX 3070, RTX 4070, RX 6700 style  
- **Budget**: Older RTX 2000/RTX 3000 or entry-level cards
- Search terms: "graphics card", "nvidia rtx", "discrete gpu"

### CPU (Processors)
- **High-end**: i9, Ryzen 9 style
- **Mid-range**: i7, Ryzen 7 style
- **Budget**: i5, Ryzen 5 style
- Search terms: "CPU", "processor", "intel", "AMD Ryzen"

### RAM (Memory)
- **High-end**: DDR5 with RGB lighting
- **Mid-range**: DDR4/5 standard design
- **Budget**: DDR3 or older style
- Search terms: "RAM", "memory module", "DDR5", "DDR4"

### Storage (SSD/HDD)
- **Fast**: NVMe M.2 (tiny, thin form factor)
- **Medium**: 2.5" SSD (flat, laptop-sized)
- **Traditional**: 3.5" HDD (large, mechanical)
- Search terms: "SSD", "hard drive", "NVMe", "M.2"

### Cooling (CPU Coolers)
- **Air Tower**: Large tower-style cooler with many fins
- **Liquid**: All-in-one water cooler with pump and radiator
- **Compact**: Low-profile cooler for small cases
- Search terms: "CPU cooler", "heatsink", "water cooler AIO"

## Integration

Once models are in place:

1. **Load automatically**: No code changes needed if using `variant-{N}.gltf` naming
2. **Manual adjustment** (if needed): Edit `lib/model-manifest.ts`
   - `COMPONENT_POSITIONS`: x, y, z placement
   - `COMPONENT_SCALES`: size multiplier

3. **Test**:
   ```bash
   npm run dev
   # Visit: http://localhost:3000/configure/gaming-rig
   ```

4. **Optimize** (if file > 2MB):
   ```bash
   npm install -g @gltf-transform/cli
   gltf-transform compress model.gltf model.glb
   ```

## Performance Tips

- **File size**: Aim for 300-800KB per model
- **Textures**: Embed in .glb format where possible
- **Caching**: Models cached after first load (instant swap after)
- **Preloading**: All models preload on startup

## Troubleshooting

**Model doesn't load?**
- Check browser console (F12 → Console)
- Verify file path matches `lib/model-manifest.ts`
- Ensure file exists in correct folder
- Validate glTF format: https://gltf.report/

**Model too small/large?**
- Adjust `COMPONENT_SCALES` in `lib/model-manifest.ts`
- Or rescale model in Blender before uploading

**Performance issues?**
- Reduce model file sizes using Draco compression
- Check total loaded size in DevTools → Network tab

## Resources

- **Sketchfab**: https://sketchfab.com
- **Model Licenses**: https://sketchfab.com/licenses
- **glTF Viewer**: https://gltf.report/
- **Compression Tool**: https://www.npmjs.com/package/@gltf-transform/cli

## Current Status

- **Directory structure**: ✓ Ready
- **Sample models**: Placeholder procedurally-generated models (replace with real models)
- **Total placeholders**: 14 models (GPU: 3, CPU: 3, RAM: 3, Storage: 3, Cooling: 2)

## Next Steps

1. Read **`MODEL_SOURCING_GUIDE.md`** for detailed instructions
2. Download 1-2 hero models from Sketchfab
3. Place in appropriate `variant-{N}.gltf` files
4. Test in configurator
5. Iterate and refine
6. Deploy when ready

---

**Need help?** See `MODEL_SOURCING_GUIDE.md` for comprehensive documentation including:
- Step-by-step sourcing process
- Recommended Sketchfab searches
- File optimization techniques
- Integration workflow
- Performance best practices
- FAQ and troubleshooting
