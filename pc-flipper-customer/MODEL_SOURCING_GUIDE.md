# 3D Model Sourcing Guide for FlipFlop Configurator

## Overview

This guide explains how to source real, high-quality 3D models from Sketchfab and integrate them into the FlipFlop 3D PC configurator. With the right models, your configurator will look professional and help customers visualize their custom builds.

## Why Sketchfab?

Sketchfab is the best free source for 3D models because:

- **Free CC-licensed models**: Thousands of models available under Creative Commons licenses (CC0, CC-BY, etc.) that are safe to use commercially
- **High-quality assets**: Models created by professional 3D artists, not procedurally generated
- **glTF/GLB export**: Most models can be downloaded in glTF or GLB format, which is perfect for web browsers
- **Active community**: New models added regularly with curated collections
- **Searchable by component**: Can find realistic PC components by searching for specific hardware

## Model Requirements

Before downloading, ensure models meet these specifications:

| Requirement | Specification | Why? |
|---|---|---|
| Format | glTF (.gltf) or GLB (.glb) | Best web performance, standard format for Three.js |
| Max Size | 2MB per model | Fits in browser cache, fast downloads |
| Recommended Size | 200-800KB | Best balance of quality and performance |
| License | CC-licensed (CC0, CC-BY, etc.) | Legal to use commercially |
| Scale | Roughly 1 unit = ~1 inch | Consistency with PC components |
| Origin | Centered at (0, 0, 0) | Correct positioning in scene |
| Textures | Embedded when possible | Reduces separate file requests |

## Recommended Models by Component Type

### GPU (Graphics Card) — 3 Variants

Graphics cards are the most visually prominent component. Aim for realistic, recognizable designs.

#### Option 1: High-End GPU (RTX 4090 style)
- **Search terms**: 
  - "nvidia rtx graphics card"
  - "RTX 4090"
  - "GeForce graphics card"
  - "discrete GPU nvidia"
- **What to look for**: 
  - Realistic dual/triple fan cooler design
  - Prominent heatsink and power connectors
  - Modern aesthetic (2020+)
- **Expected file size**: 300-900KB
- **Alternative searches**: "high-end gpu", "gaming graphics card", "nvidia discrete"

#### Option 2: Mid-Range GPU (RTX 3070 style)
- **Search terms**:
  - "graphics card gaming"
  - "GPU mid range"
  - "geforce 3070"
  - "nvidia gaming card"
- **What to look for**:
  - Dual fan cooler design (simpler than high-end)
  - Good balance of detail and simplicity
  - Professional appearance
- **Expected file size**: 250-700KB
- **Alternative searches**: "mid tier gpu", "budget gaming graphics", "RTX 3060"

#### Option 3: Budget GPU (Older/Entry-level)
- **Search terms**:
  - "graphics card old"
  - "budget gpu"
  - "vintage graphics card"
  - "entry level gpu"
- **What to look for**:
  - Simpler fan design (single fan)
  - Older aesthetic (retro style works here)
  - Lower polygon count acceptable
- **Expected file size**: 150-500KB
- **Alternative searches**: "legacy gpu", "older graphics card", "entry graphics"

**Tips for GPU models:**
- Look for models with visible details like fans, heatsinks, and connectors
- Avoid models that are overly stylized or cartoonish
- Check the preview to ensure dual/triple fans are modeled accurately
- File should include both plastic and metal materials

---

### CPU (Processor) — 3 Variants

CPU models should ideally include the heatsink or cooler mounting. Look for realistic semiconductor designs.

#### Option 1: High-End Processor (i9/Ryzen 9)
- **Search terms**:
  - "intel core i9"
  - "AMD Ryzen 9"
  - "CPU processor socket"
  - "processor with heatsink"
- **What to look for**:
  - CPU chip with visible socket/pins
  - Optional: heatsink attached
  - Modern rectangular design
  - Dark substrate color
- **Expected file size**: 300-900KB
- **Alternative searches**: "high end processor", "intel processor", "ryzen cpu"

#### Option 2: Mid-Range Processor (i7/Ryzen 7)
- **Search terms**:
  - "intel i7"
  - "AMD Ryzen 7"
  - "cpu chip"
  - "processor cpu"
- **What to look for**:
  - Detailed CPU die representation
  - Visible PGA/LGA socket details
  - Good balance of detail
- **Expected file size**: 250-700KB
- **Alternative searches**: "mid range cpu", "desktop processor", "ryzen 7"

#### Option 3: Budget Processor (i5/Ryzen 5)
- **Search terms**:
  - "budget processor"
  - "cpu simple"
  - "entry level cpu"
  - "intel i5"
- **What to look for**:
  - Simplified geometry but still recognizable
  - Basic socket design
  - Good for budget configurations
- **Expected file size**: 150-500KB
- **Alternative searches**: "affordable cpu", "entry processor", "basic cpu"

**Tips for CPU models:**
- CPU models can be very small, so detail matters less than for GPU
- If the model is too simple, it will look odd next to detailed GPUs
- Look for IHS (Integrated Heat Spreader) detail if possible
- Models with visible socket pins are more realistic

---

### RAM (Memory Module) — 3 Variants

RAM models should have recognizable DIMM form factors. Look for modern DDR4/DDR5 designs.

#### Option 1: High-End RAM (DDR5 RGB)
- **Search terms**:
  - "DDR5 memory"
  - "DDR5 RAM stick"
  - "RAM RGB"
  - "memory module ddr5"
- **What to look for**:
  - Modern DIMM form factor (vertical stick)
  - RGB lighting elements (optional but visually interesting)
  - Black or silver color scheme
  - Detailed heatspreader
- **Expected file size**: 150-500KB
- **Alternative searches**: "high speed memory", "ddr5 stick", "rgb ram"

#### Option 2: Mid-Range RAM (DDR4/DDR5 standard)
- **Search terms**:
  - "DDR4 memory"
  - "memory stick"
  - "RAM module"
  - "computer memory"
- **What to look for**:
  - Standard UDIMM form factor
  - Clean heatspreader design
  - Professional appearance
  - No RGB (simpler design)
- **Expected file size**: 100-400KB
- **Alternative searches**: "standard ram", "dimm memory", "ddr4"

#### Option 3: Budget/Old RAM (DDR3 or older)
- **Search terms**:
  - "DDR3 memory"
  - "old RAM"
  - "legacy memory stick"
  - "retro RAM"
- **What to look for**:
  - Legacy DIMM design (shorter than DDR4)
  - Older aesthetic is fine here
  - Simpler geometry acceptable
- **Expected file size**: 50-250KB
- **Alternative searches**: "older memory", "vintage ram", "ddr3"

**Tips for RAM models:**
- RAM is small, so make sure the model isn't too detailed (file size matters more)
- Multiple sticks can be arranged together in the scene
- RGB lighting can be faked with emissive materials
- Simpler models often look better for RAM at this scale

---

### Storage (SSD/HDD) — 3 Variants

Storage models should represent different form factors: M.2 NVMe, 2.5" SSD, and 3.5" HDD.

#### Option 1: NVMe M.2 SSD (Fastest, smallest)
- **Search terms**:
  - "NVMe SSD"
  - "M.2 drive"
  - "nvme ssd model"
  - "m.2 storage"
- **What to look for**:
  - Thin rectangular form factor (22x80mm typical)
  - Modern design with heat spreader
  - Dark color (usually black/gray)
  - Gold connector pins visible
- **Expected file size**: 50-300KB
- **Alternative searches**: "nvme drive", "m.2 ssd model", "fast ssd"

#### Option 2: 2.5" SSD (Laptop-sized)
- **Search terms**:
  - "2.5 inch SSD"
  - "2.5 SSD model"
  - "laptop ssd"
  - "ssd drive"
- **What to look for**:
  - Flat rectangular form factor (2.5" × 3.8" typical)
  - Similar to small book/card
  - Professional casing design
  - Visible SATA or USB connectors
- **Expected file size**: 100-400KB
- **Alternative searches**: "2.5 ssd", "portable ssd", "laptop storage"

#### Option 3: 3.5" HDD (Traditional mechanical)
- **Search terms**:
  - "hard drive"
  - "3.5 HDD"
  - "mechanical hard drive"
  - "hdd model"
- **What to look for**:
  - Larger rectangular form factor (5.75" × 4" typical)
  - Visible top casing and screw holes
  - Mechanical aesthetic (fan/motor visible if realistic)
  - Metal or plastic finish
- **Expected file size**: 150-600KB
- **Alternative searches**: "3.5 hard drive", "mechanical drive", "hdd"

**Tips for Storage models:**
- Form factor is key — M.2 should look tiny, HDD should look large
- Different storage types provide nice visual variety in the configurator
- Mechanical drives can have more detail than SSDs
- Color variation helps distinguish them in the scene

---

### Cooling (CPU Cooler) — 2-3 Variants

Cooling solutions are visually prominent. Choose from air coolers and liquid coolers.

#### Option 1: High-End Air Cooler (Tower-style)
- **Search terms**:
  - "CPU cooler"
  - "tower cooler"
  - "noctua cooler"
  - "cpu heatsink"
- **What to look for**:
  - Large tower design (100-150mm tall)
  - Multiple aluminum fins (very detailed)
  - Prominent top fan
  - Professional branding/aesthetics
- **Expected file size**: 500KB-1.5MB
- **Performance note**: These are larger models, optimize if > 1MB
- **Alternative searches**: "air cooler cpu", "tower heatsink", "large cpu cooler"

#### Option 2: Liquid Cooler (All-in-One AIO)
- **Search terms**:
  - "liquid cooler"
  - "water cooler AIO"
  - "AIO cooler"
  - "all in one cooler"
- **What to look for**:
  - Pump block (small rectangular with fan)
  - Long tubes connecting to radiator
  - Radiator with multiple fans
  - Modern aesthetic (RGB possible)
- **Expected file size**: 400KB-1.5MB
- **Performance note**: Can be large due to radiator, compress if needed
- **Alternative searches**: "aio cooler", "custom water cooling", "radiator cooler"

#### Option 3: Low-Profile/Compact Cooler (Optional)
- **Search terms**:
  - "low profile cooler"
  - "compact cooler"
  - "small cpu cooler"
  - "downdraft cooler"
- **What to look for**:
  - Minimal height (< 80mm)
  - Single or dual fans
  - Good for SFF (Small Form Factor) builds
  - Compact aesthetic
- **Expected file size**: 200-800KB
- **Alternative searches**: "budget cooler", "ITX cooler", "passive cooler"

**Tips for Cooling models:**
- Cooling is one of the most visually interesting components
- Large air coolers with detailed fins look impressive
- Liquid coolers with visible tubing are very eye-catching
- Make sure cooler scale makes sense relative to CPU below it

---

## How to Download Models from Sketchfab

### Step 1: Visit Sketchfab
Navigate to https://sketchfab.com in your browser.

### Step 2: Search for a Model
1. Use the search box at the top
2. Enter search terms (e.g., "RTX 4090" or "CPU cooler")
3. Press Enter to search

### Step 3: Filter by Availability & License
1. Click "More" under the search filters
2. Set filters:
   - **Downloadable**: Yes (must be able to download)
   - **License**: Select CC0 and/or CC-BY variants (these are free to use)
3. Apply filters

### Step 4: Preview Models
1. Scroll through results
2. Click on interesting models to preview
3. Check:
   - Does it look realistic and detailed?
   - Is it the right component type?
   - Is the file size reasonable (shown on page)?

### Step 5: Download
1. Click the **Download** button (usually bottom-right of 3D viewer)
2. Select **glTF** format (not .blend or other formats)
3. Save the ZIP file
4. Extract the ZIP file
5. Look for the `.gltf` file (might also see `.bin` or `.glb` in the same folder)

### Step 6: Verify the Download
After extracting:
- Should have at least one `.gltf` or `.glb` file
- May have accompanying `.bin` files (binary data for the model)
- May have separate texture files (`.png`, `.jpg`)
- All files in the same folder should be kept together

---

## Integration Steps

### Step 1: Download Multiple Models
For each component type, download 2-3 models with different variants/styles. This gives users choices in the configurator.

**Recommended downloads:**
- GPU: 3 models (high-end, mid-range, budget)
- CPU: 3 models (high-end, mid-range, budget)
- RAM: 3 models (DDR5, DDR4, DDR3/budget)
- Storage: 3 models (M.2, 2.5" SSD, 3.5" HDD)
- Cooling: 2-3 models (air tower, liquid cooler, compact)

**Total: 14-15 models for a complete configurator**

### Step 2: Organize Downloaded Files
Create a folder structure on your computer:
```
downloaded_models/
├── gpu/
│   ├── rtx-4090/
│   │   ├── model.gltf
│   │   ├── model.bin
│   │   └── textures/ (if present)
│   ├── rtx-3070/
│   │   └── ...
│   └── budget-gpu/
│       └── ...
├── cpu/
│   ├── i9/
│   │   └── ...
│   ├── i7/
│   │   └── ...
│   └── i5/
│       └── ...
├── ram/
│   └── ...
├── storage/
│   └── ...
└── cooling/
    └── ...
```

### Step 3: Place Models in Project
Copy the `.gltf` files (and any `.bin` files) into the FlipFlop project:

```bash
# From your downloaded_models folder:
cp downloaded_models/gpu/rtx-4090/model.gltf \
   /path/to/FlipFlop/pc-flipper-customer/public/models/gpu/variant-1.gltf

cp downloaded_models/gpu/rtx-3070/model.gltf \
   /path/to/FlipFlop/pc-flipper-customer/public/models/gpu/variant-2.gltf

cp downloaded_models/gpu/budget-gpu/model.gltf \
   /path/to/FlipFlop/pc-flipper-customer/public/models/gpu/variant-3.gltf

# Repeat for other component types...
```

**File structure in project:**
```
public/models/
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

### Step 4: Handle Dependent Files
If a model has `.bin` files or textures:
1. **Recommended**: Keep `.bin` files in the same folder as `.gltf`
2. **Optional**: Embed textures to avoid separate file requests

To convert a `.gltf` with separate files to self-contained `.glb`:
- Use [glTF-Transform CLI](https://www.npmjs.com/package/@gltf-transform/cli): `gltf-transform import model.gltf model.glb`
- Or use online tools like [Don McCurdy's glTF viewer](https://gltf.report/) with export option

### Step 5: Update Model Manifest (Optional)
The `lib/model-manifest.ts` is already set up to use this naming convention. No changes needed unless:
- You want to use different filenames
- You want to customize positioning/scaling per model

**Default manifest already configured:**
```typescript
export const MODEL_URLS: Record<string, Record<number, string>> = {
  gpu: {
    1: '/models/gpu/variant-1.gltf',
    2: '/models/gpu/variant-2.gltf',
    3: '/models/gpu/variant-3.gltf',
  },
  // ... other components
};
```

### Step 6: Test in Configurator
1. Start the dev server:
   ```bash
   npm run dev
   ```
2. Navigate to the configurator:
   - URL: `http://localhost:3000/configure/gaming-rig` (or similar)
3. Use the component selector to swap between variants
4. Verify:
   - Models load correctly
   - Sizing looks right
   - No console errors
   - Performance is acceptable

### Step 7: Fine-Tune Positioning (If Needed)
If models need repositioning or rescaling:
1. Edit `lib/model-manifest.ts`
2. Adjust `COMPONENT_POSITIONS` for x/y/z placement
3. Adjust `COMPONENT_SCALES` for sizing
4. Refresh browser to see changes

Example adjustments:
```typescript
export const COMPONENT_POSITIONS: Record<string, { x: number; y: number; z: number }> = {
  gpu: { x: 2.5, y: 0.5, z: -0.5 },  // Move GPU further right
  cpu: { x: 0, y: 0.5, z: 0.5 },      // CPU centered
  // ... adjust as needed
};

export const COMPONENT_SCALES: Record<string, number> = {
  gpu: 1.2,  // Make GPU 20% larger
  cpu: 0.8,
  // ... adjust as needed
};
```

---

## Performance Optimization

### File Size Management

**Problem**: Large models slow down page loads and use more browser memory.

**Solution - Compression:**
1. **Draco Compression** (recommended):
   - Reduces `.gltf` file size by 75-90%
   - Tool: [glTF-Transform CLI](https://www.npmjs.com/package/@gltf-transform/cli)
   - Command: `gltf-transform compress model.gltf model-compressed.glb`
   - Result: Transparent to end users

2. **Polygon Reduction**:
   - Decimate mesh if model has excessive detail
   - Tools: Blender, Meshlab, glTF-Transform
   - Goal: < 500KB per model

3. **Texture Optimization**:
   - Embed textures in `.glb` format
   - Resize textures to 1024x1024 or smaller
   - Use WebP format if browser supports

### Caching Strategy

Models are automatically cached by browsers:
- **First load**: Downloaded from network
- **Subsequent loads**: Loaded from browser cache instantly
- **Cache size**: All models combined should fit in browser memory

### Lazy Loading (Advanced)

By default, all models preload on startup. For many models:
1. Move preloading to demand (when user selects component)
2. Show loading spinner while model downloads
3. Reduces initial page load time

---

## Troubleshooting

### Problem: Model doesn't load
**Symptoms**: Blank space where model should be, or console error

**Solutions**:
1. Check browser console (F12 → Console tab)
2. Verify file exists: `public/models/{type}/variant-{N}.gltf`
3. Check file path in `model-manifest.ts`
4. Ensure model is valid glTF (try in [glTF viewer](https://www.khronos.org/gltf/viewers/))
5. Check CORS headers if hosting externally

### Problem: Model appears tiny or huge
**Symptoms**: Model is disproportionate to other components

**Solutions**:
1. Adjust scale in `COMPONENT_SCALES`:
   ```typescript
   export const COMPONENT_SCALES: Record<string, number> = {
     gpu: 1.2,  // Increase to 1.5 to make bigger
     cpu: 0.8,
   };
   ```
2. Or rescale model before uploading:
   - Open in Blender: `File → Import → glTF (.glb/.gltf)`
   - Scale: `S` key, type number (e.g., `0.5` to halve)
   - Export: `File → Export → glTF 2.0`

### Problem: Performance is sluggish
**Symptoms**: Slow frame rate, lag when swapping models

**Solutions**:
1. Reduce model file sizes (see "Performance Optimization" above)
2. Check total loaded model size: Open DevTools → Network tab
3. Disable unnecessary models (remove variants you're not using)
4. Profile performance: DevTools → Performance tab → Record interaction
5. Consider reducing scene complexity (fewer 3D objects elsewhere)

### Problem: Model has wrong orientation or positioning
**Symptoms**: Model is rotated or positioned incorrectly

**Solutions**:
1. Adjust position in `COMPONENT_POSITIONS`:
   ```typescript
   gpu: { x: 2, y: 0.5, z: -0.5 },  // x=right, y=up, z=forward
   ```
2. Or rotate model before uploading:
   - In Blender: `R` key, choose axis (X/Y/Z), type angle
   - Export as glTF

### Problem: Model files are separated (`.bin`, textures, etc.)
**Symptoms**: Downloaded model has multiple files

**Solutions**:
1. Keep all files in same folder (they link to each other)
2. Or convert to self-contained `.glb`:
   ```bash
   npm install -g @gltf-transform/cli
   gltf-transform import model.gltf model.glb
   ```

---

## Recommended Workflow

### Timeline
A realistic timeline for sourcing and integrating models:

**Day 1 - Research (2-3 hours)**
- Search Sketchfab for promising models
- Download 1-2 "hero" models per component type (the best-looking ones)
- Test loading them in the configurator
- Identify any that need rescaling or repositioning

**Day 2 - Download & Organize (1-2 hours)**
- Download additional variants (2-3 per component)
- Organize files locally
- Optimize file sizes if needed
- Copy to `public/models/` directory

**Day 3 - Integration & Testing (2-4 hours)**
- Test each component in the configurator
- Fine-tune positioning and scaling
- Verify performance is acceptable
- Take screenshots for documentation

**Day 4 - Polish & Launch (1-2 hours)**
- Update README or model documentation
- Commit changes
- Deploy to production
- Monitor for issues

**Total: 6-11 hours** (depending on how perfectionist you want to be)

---

## Resources & Links

### Sketchfab
- **Main site**: https://sketchfab.com
- **License info**: https://sketchfab.com/licenses
- **CC0 models**: https://sketchfab.com/search?q=&type=models&license=CC0
- **CC-BY models**: https://sketchfab.com/search?type=models&license=CC-BY

### glTF Tools & Specs
- **glTF Specification**: https://www.khronos.org/gltf/ (official standard)
- **glTF Sample Models**: https://github.com/KhronosGroup/glTF-Sample-Models
- **Don McCurdy's glTF Viewer**: https://gltf.report/ (test & convert models)
- **glTF-Transform**: https://www.npmjs.com/package/@gltf-transform/cli (compress/optimize)

### Free Model Resources
- **Sketchfab**: https://sketchfab.com (best for PC components)
- **TurboSquid Free**: https://www.turbosquid.com/Search/3D-Models/free
- **CGTrader Free**: https://www.cgtrader.com/free-3d-models
- **Poly Haven**: https://polyhaven.com/models (excellent quality)

### Learning & Documentation
- **Three.js GLTFLoader**: https://threejs.org/docs/index.html#examples/en/loaders/GLTFLoader
- **glTF Best Practices**: https://www.khronos.org/gltf/guidelines/
- **Web Performance**: https://web.dev/performance/

---

## FAQ

**Q: Do I need a Sketchfab account to download models?**
A: No, free CC-licensed models can be downloaded without an account. Creating an account is optional but useful for saving favorites.

**Q: Can I use any model I find on Sketchfab?**
A: Only if the license is CC0 or CC-BY (or similar free commercial-use license). Check the license before downloading.

**Q: What format should I download?**
A: Download **glTF** or **GLB** format. These are web-optimized and work best with Three.js.

**Q: My model is 5MB, is that too large?**
A: Yes, aim for < 2MB. Use Draco compression or polygon reduction to optimize.

**Q: Can I use paid models?**
A: You could, but Sketchfab's free CC-licensed models are usually sufficient and always allow commercial use.

**Q: What if a model has separate texture files?**
A: You can either:
1. Keep `.bin` and texture files in the same folder (they'll link automatically)
2. Convert to `.glb` format which embeds everything in one file

**Q: Can I edit models after downloading?**
A: Yes, open them in Blender (free) or other 3D editors. You can rescale, reposition, or modify materials.

**Q: Do models need to be textured?**
A: No, but textured models look much better. Some procedurally generated models have no textures and still look decent.

**Q: How many variants should I have per component?**
A: 2-3 is ideal. More gives users choice, but more files to manage. Fewer is simpler but less variety.

**Q: Will this work on mobile devices?**
A: Yes, Three.js GLTFLoader works on mobile browsers. Models will be smaller on mobile displays.

---

## Contributing

Found a great model on Sketchfab? Share it with the team:
1. Note the Sketchfab URL and artist name
2. Add to the recommendations in this guide
3. Test it in the configurator
4. Credit the artist in your commit message

Example:
```
feat(models): add RTX 4090 GPU model from Sketchfab
- Model by [Artist Name] (https://sketchfab.com/models/[ID])
- License: CC-BY
- File size: 650KB after compression
```

---

## Next Steps

1. **Choose your first component**: Pick GPU or CPU to start
2. **Find 1-2 hero models**: Search Sketchfab and preview
3. **Download**: Get the glTF version
4. **Test**: Place in `public/models/gpu/` and load in configurator
5. **Iterate**: Fine-tune scale/position
6. **Repeat**: Do other component types
7. **Launch**: Deploy when all components look good

Good luck building an amazing 3D configurator! Questions? Check the troubleshooting section or review the React code in `components/ModelViewer.tsx`.
