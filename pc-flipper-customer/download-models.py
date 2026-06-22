#!/usr/bin/env python3
"""
FlipFlop 3D Model Downloader
Downloads recommended free CC-licensed models from Sketchfab
"""

import os
import subprocess
import json
import sys
from pathlib import Path

# Recommended models with direct information
# Format: {component_type: [variant_dict]}
RECOMMENDED_MODELS = {
    "gpu": [
        {
            "name": "RTX 4090",
            "variant": 1,
            "search": "graphics card high-end",
            "notes": "High-end GPU - search Sketchfab for 'RTX 4090' or 'nvidia high end'"
        },
        {
            "name": "GTX Mid-Range",
            "variant": 2,
            "search": "graphics card mid range",
            "notes": "Mid-range GPU - search 'GTX' or 'mid-range graphics card'"
        },
        {
            "name": "Budget GPU",
            "variant": 3,
            "search": "graphics card budget",
            "notes": "Budget GPU - search 'older graphics card' or 'budget gpu'"
        }
    ],
    "cpu": [
        {
            "name": "Intel i9 with cooler",
            "variant": 1,
            "search": "cpu cooler tower",
            "notes": "High-end CPU - search 'CPU cooler' or 'processor tower cooler'"
        },
        {
            "name": "Intel i7/Ryzen 7",
            "variant": 2,
            "search": "cpu processor mid",
            "notes": "Mid-range CPU - search 'computer processor' or 'cpu'"
        },
        {
            "name": "Budget CPU",
            "variant": 3,
            "search": "processor simple",
            "notes": "Budget CPU - search 'budget cpu' or 'simple processor'"
        }
    ],
    "ram": [
        {
            "name": "DDR5 RGB",
            "variant": 1,
            "search": "DDR5 RAM RGB",
            "notes": "High-end RAM - search 'DDR5 memory' or 'RAM RGB'"
        },
        {
            "name": "DDR4 Standard",
            "variant": 2,
            "search": "DDR4 memory",
            "notes": "Mid-range RAM - search 'DDR4' or 'memory stick'"
        },
        {
            "name": "DDR3 Budget",
            "variant": 3,
            "search": "DDR3 memory",
            "notes": "Budget RAM - search 'DDR3' or 'old RAM'"
        }
    ],
    "storage": [
        {
            "name": "NVMe M.2 SSD",
            "variant": 1,
            "search": "NVMe SSD",
            "notes": "Fast storage - search 'NVMe' or 'M.2 SSD'"
        },
        {
            "name": "2.5 inch SSD",
            "variant": 2,
            "search": "SSD 2.5 inch",
            "notes": "Mid storage - search '2.5 SSD' or 'laptop ssd'"
        },
        {
            "name": "3.5 inch HDD",
            "variant": 3,
            "search": "hard drive 3.5",
            "notes": "Traditional storage - search 'hard drive' or 'HDD'"
        }
    ],
    "cooling": [
        {
            "name": "Tower Air Cooler",
            "variant": 1,
            "search": "CPU cooler tower",
            "notes": "High-end cooling - search 'CPU cooler' or 'noctua cooler'"
        },
        {
            "name": "Liquid AIO Cooler",
            "variant": 2,
            "search": "liquid cooler AIO",
            "notes": "Modern cooling - search 'liquid cooler' or 'AIO cooler'"
        }
    ]
}

def setup_directories():
    """Create model directories if they don't exist"""
    base_path = Path("public/models")
    for component_type in RECOMMENDED_MODELS.keys():
        (base_path / component_type).mkdir(parents=True, exist_ok=True)
    print("OK: Directories created")

def print_shopping_list():
    """Print formatted shopping list for user to manually download"""
    print("\n" + "="*70)
    print("SKETCHFAB MODEL SHOPPING LIST")
    print("="*70)
    print("\nTo download models, visit Sketchfab and search for each:\n")

    for component_type, models in RECOMMENDED_MODELS.items():
        print(f"\nCOMPONENT: {component_type.upper()}")
        print("-" * 70)
        for model in models:
            print(f"\n  Variant {model['variant']}: {model['name']}")
            print(f"  Search: {model['search']}")
            print(f"  → {model['notes']}")
            print(f"  Place in: public/models/{component_type}/variant-{model['variant']}.gltf")

def check_existing_models():
    """Check which models are already in place"""
    print("\n" + "="*70)
    print("EXISTING MODELS")
    print("="*70)

    base_path = Path("public/models")
    total_size = 0
    file_count = 0

    for component_type in sorted(RECOMMENDED_MODELS.keys()):
        component_dir = base_path / component_type
        if component_dir.exists():
            files = list(component_dir.glob("*.gltf")) + list(component_dir.glob("*.glb"))
            if files:
                print(f"\n{component_type.upper()}: {len(files)} file(s)")
                for f in sorted(files):
                    size_kb = f.stat().st_size / 1024
                    total_size += f.stat().st_size
                    file_count += 1
                    print(f"  OK: {f.name} ({size_kb:.1f}KB)")
            else:
                print(f"\n{component_type.upper()}: No files yet")

    if file_count > 0:
        print(f"\nStatus: {file_count} files, {total_size/1024/1024:.2f}MB")
    else:
        print("\nStatus: No models downloaded yet")

def create_testing_guide():
    """Create a testing guide"""
    guide = """
===============================================================================
TESTING YOUR MODELS
===============================================================================

Once you've placed all models in public/models/:

1. Start dev server:
   cd pc-flipper-customer
   npm run dev -- --port 3001

2. Open configurator:
   http://andromeda-ts:3001/configure/gaming-rig

3. Test interactions:
   - Hover over 3D scene -> see component labels
   - Click component -> swap modal opens with your models
   - Drag to rotate the 3D scene
   - Select different tiers -> see different models load

4. Check browser console:
   - No error messages = success
   - Red errors about loading models = check file paths

===============================================================================
"""
    print(guide)

def main():
    print("""
================================================================================
                   FlipFlop 3D Model Downloader

 This script helps organize your downloaded Sketchfab models.
================================================================================
    """)

    # Step 1: Setup directories
    print("\n[1/4] Setting up directories...")
    setup_directories()

    # Step 2: Show shopping list
    print("\n[2/4] Generating shopping list...")
    print_shopping_list()

    # Step 3: Check existing models
    print("\n[3/4] Checking existing models...")
    check_existing_models()

    # Step 4: Show testing guide
    print("\n[4/4] Testing guide...")
    create_testing_guide()

    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("""
1. Visit: https://sketchfab.com
2. For each model in the shopping list above:
   - Search for the model (e.g., "RTX 4090")
   - Filter: License = CC0 or CC-BY, Downloadable = Yes
   - Download the glTF or GLB version
   - Extract ZIP if needed
   - Place in: public/models/{type}/variant-{N}.gltf

3. Run this script again to verify:
   python3 download-models.py

4. Start dev server and test:
   npm run dev -- --port 3001
   Open: http://andromeda-ts:3001/configure/gaming-rig

Estimated time: 15-30 minutes to download and place all 14 models

Questions? Check MODEL_SHOPPING_LIST.md for detailed instructions
    """)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nAborted.")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
