# 3D Component Models

This directory contains glTF/GLB 3D models for PC components displayed in the 3D configurator.

## Placeholder Models

Currently using procedurally generated placeholder models for testing. Each component type has 2-3 variants with distinct colors:
- GPU: Green variants (accent color)
- CPU: Yellow variants
- RAM: Blue variants
- Storage: Indigo variants
- Cooling: Red variants

## To Add Real Models

1. Visit https://sketchfab.com
2. Search for free CC-licensed models:
   - GPU: "graphics card" or specific models (RTX 4090, RX 7900, RTX 4080)
   - CPU: "Intel processor", "AMD Ryzen", or "CPU chip"
   - RAM: "memory module", "DDR5", or "DDR4"
   - Storage: "SSD", "M.2 SSD", or "hard drive"
   - Cooling: "CPU cooler", "heatsink", or "liquid cooler"

3. Download the glTF (.gltf) or GLB (.glb) version
4. Place in the appropriate subfolder: gpu/, cpu/, ram/, storage/, cooling/
5. Name files as: variant-1.gltf, variant-2.gltf, variant-3.gltf
6. No changes needed to model-manifest.ts if using the naming convention above

## Model Requirements

- Format: glTF 2.0 (.gltf or .glb)
- Max file size: 2MB per model (keep assets under 500KB when possible)
- Models should be centered at origin (0, 0, 0)
- Scale: roughly 1 unit = 1 inch (will be scaled per COMPONENT_SCALES in model-manifest.ts)
- License: CC-licensed or similar (check Sketchfab license before downloading)

## Current Models

- **gpu/**: 3 placeholder variants (green)
- **cpu/**: 3 placeholder variants (yellow)
- **ram/**: 3 placeholder variants (blue)
- **storage/**: 3 placeholder variants (indigo)
- **cooling/**: 2 placeholder variants (red)

Total: 14 placeholder models

## Tips for Sketchfab

- Filter by "Free" and license type (CC0, CC-BY, etc.)
- Look for models without complex rigging or animations
- Prefer single-mesh models or properly grouped objects
- Download the glTF version for better compatibility
- Check the model preview to ensure it displays correctly

## Integration Notes

- Models are loaded via Three.js GLTFLoader in the 3D scene
- Position and scale are applied from COMPONENT_POSITIONS and COMPONENT_SCALES in model-manifest.ts
- Models should work with standard PBR materials
