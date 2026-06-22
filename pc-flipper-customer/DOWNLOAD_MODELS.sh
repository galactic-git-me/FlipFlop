#!/bin/bash

# FlipFlop 3D Model Setup Script
# This script helps organize downloaded 3D models into the correct directory structure
#
# Usage:
#   1. Download models from Sketchfab (see MODEL_SOURCING_GUIDE.md)
#   2. Extract downloaded ZIP files
#   3. Run this script: bash DOWNLOAD_MODELS.sh
#   4. Follow the prompts to place models in the correct folders

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="$PROJECT_DIR/public/models"

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  FlipFlop 3D Model Setup & Organization Tool              ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if models directory exists
if [ ! -d "$MODELS_DIR" ]; then
    echo -e "${RED}✗ Error: models directory not found at $MODELS_DIR${NC}"
    exit 1
fi

echo -e "${YELLOW}Project directory:${NC} $PROJECT_DIR"
echo -e "${YELLOW}Models directory:${NC} $MODELS_DIR"
echo ""

# Create component subdirectories if they don't exist
COMPONENTS=("gpu" "cpu" "ram" "storage" "cooling")
for component in "${COMPONENTS[@]}"; do
    if [ ! -d "$MODELS_DIR/$component" ]; then
        mkdir -p "$MODELS_DIR/$component"
        echo -e "${GREEN}✓${NC} Created $MODELS_DIR/$component/"
    else
        echo -e "${GREEN}✓${NC} Found $MODELS_DIR/$component/"
    fi
done

echo ""
echo -e "${YELLOW}Directory structure ready!${NC}"
echo ""

# Show current model status
echo -e "${BLUE}Current Models:${NC}"
echo ""

for component in "${COMPONENTS[@]}"; do
    component_path="$MODELS_DIR/$component"
    count=$(find "$component_path" -name "*.gltf" -o -name "*.glb" | wc -l)

    echo -e "${YELLOW}$component/${NC}"

    if [ $count -eq 0 ]; then
        echo -e "  ${RED}  (no models found)${NC}"
    else
        echo -e "  ${GREEN}  ✓ $count model(s) found${NC}"
        find "$component_path" -maxdepth 1 \( -name "*.gltf" -o -name "*.glb" \) | while read -r file; do
            filename=$(basename "$file")
            filesize=$(du -h "$file" | cut -f1)
            echo -e "    • $filename (${filesize})"
        done
    fi
    echo ""
done

# Show instructions
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Next Steps                                                ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}1. Download models from Sketchfab${NC}"
echo "   • Visit: https://sketchfab.com"
echo "   • Search for PC components (GPU, CPU, RAM, etc.)"
echo "   • Download in glTF or GLB format"
echo "   • See MODEL_SOURCING_GUIDE.md for detailed instructions"
echo ""
echo -e "${GREEN}2. Extract downloaded ZIP files${NC}"
echo "   • Unzip the downloaded files"
echo "   • Look for .gltf or .glb files"
echo ""
echo -e "${GREEN}3. Copy models to project folders${NC}"
echo ""
for component in "${COMPONENTS[@]}"; do
    component_path="$MODELS_DIR/$component"
    echo "   ${YELLOW}$component:${NC}"
    echo "   cp ~/Downloads/your-model.gltf $component_path/variant-1.gltf"
    echo "   cp ~/Downloads/your-model-2.gltf $component_path/variant-2.gltf"
    echo "   cp ~/Downloads/your-model-3.gltf $component_path/variant-3.gltf"
    echo ""
done

echo -e "${GREEN}4. Test in configurator${NC}"
echo "   • Run: npm run dev"
echo "   • Visit: http://localhost:3000/configure/gaming-rig"
echo "   • Test each component type and variant"
echo ""

echo -e "${GREEN}5. Optimize if needed${NC}"
echo "   • If models are > 2MB, use Draco compression:"
echo "   • npm install -g @gltf-transform/cli"
echo "   • gltf-transform compress model.gltf model-compressed.glb"
echo ""

# Offer to show detailed guide
echo -e "${YELLOW}📖 Full sourcing guide:${NC} MODEL_SOURCING_GUIDE.md"
echo ""

# Check for any issues
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Diagnostic Info                                           ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if model-manifest.ts exists
if [ -f "$PROJECT_DIR/lib/model-manifest.ts" ]; then
    echo -e "${GREEN}✓${NC} model-manifest.ts found (no changes needed)"
else
    echo -e "${RED}✗${NC} model-manifest.ts not found (required for loading models)"
fi

# Check if node_modules exists
if [ -d "$PROJECT_DIR/node_modules" ]; then
    echo -e "${GREEN}✓${NC} node_modules found (dependencies installed)"
else
    echo -e "${YELLOW}⚠${NC} node_modules not found (run: npm install)"
fi

# Check for Next.js package.json
if [ -f "$PROJECT_DIR/package.json" ]; then
    echo -e "${GREEN}✓${NC} package.json found (Next.js project)"
else
    echo -e "${RED}✗${NC} package.json not found"
fi

echo ""
echo -e "${GREEN}✓ Setup complete! You're ready to add models.${NC}"
echo ""
echo -e "Questions? See ${YELLOW}MODEL_SOURCING_GUIDE.md${NC} for detailed instructions."
echo ""
