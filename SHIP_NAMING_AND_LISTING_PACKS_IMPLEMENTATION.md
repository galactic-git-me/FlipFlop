# Ship Naming & Listing Packs Implementation Plan

**Branch**: `cursor/curated-playbooks-storefront-13ea`  
**Status**: 🚧 Ship Naming ✅ Complete | Listing Packs ⏳ Pending | Personalised Portal ⏳ Pending  
**PR**: [#12](https://github.com/galactic-git-me/FlipFlop/pull/12)

## Overview

Implements Michael's high-priority requirements:
1. **Star Trek ship naming** for curated playbooks (Base/Pro/Ultra)
2. **Listing packs** for curated playbooks (reusing pre-built pipeline)
3. **Personalised build portal** with completed 3D models
4. **Performance + spec HTML → images** (reusing existing tools)

---

## 1. Ship Naming (✅ IMPLEMENTED)

### Naming Scheme

**PUBLIC DISPLAY PATTERN**: `{Ship Name} [{Suffix}]`

**Tier Display (Customer-Facing)**:
- **Budget** → Just ship name, no suffix (e.g., "Reliant")
- **Mid-range** → Ship + " Pro" (e.g., "Reliant Pro")
- **High-end** → Ship + " Ultra" (e.g., "Reliant Ultra")

**⚠️ IMPORTANT**: DO NOT use "Base" in customer-facing UI, listing packs, performance/spec HTML, or registration cards. Internal data model can still use Budget/Mid-range/High-end.

**Ship Names Stamped by BuildBot**:
- **Latest**: Approval queue ids **122-145** (with `display_name` field, no "Base")
- **Supersedes**: ids 98-121 (deprecated - had "Base" naming)
- Customer-facing copy MUST use `display_name` field when present from approved payloads.

### Customer Type → Ship Name Mapping

| Customer Type | Ship Name | Series | Example (Mid-range) |
|---------------|-----------|--------|---------------------|
| AI Workstation | Enterprise | TNG | Enterprise Pro |
| High-performance Gaming | Defiant | DS9 | Defiant Pro |
| Great-value Gaming | Reliant | TOS/TNG | Reliant Pro |
| Student Hybrid | Voyager | VOY | Voyager Pro |
| Business & Office | Excelsior | TOS/TNG | Excelsior Pro |
| Content Creation | Galaxy | TNG | Galaxy Pro |
| Software Development | Titan | Picard/Lower Decks | Titan Pro |
| Family & Home | Stargazer | TNG/Picard | Stargazer Pro |

### Special Cases

**FF-AIW-03** (AI Workstation High-end):
- Display name: **"Enterprise Ultra"**
- Subtitle: "Bespoke Configuration"
- Note: Consult-only, Ultra tier reserved for this bespoke build

**Prometheus** (Pre-built):
- Keeps its unique name (not renamed to "Defiant Pro")
- Distinct from curated playbooks

### Implementation

**Backend** (flipflop-api):

**New Files**:
1. `data/ship_names.json` - Configuration (allows name changes without code)
2. `app/services/ship_naming.py` - Ship naming service

**Key Functions**:
```python
def get_ship_name(segment: str, tier: str) -> str
    """Get ship name with suffix (e.g., "Miranda Pro")"""

def get_ship_display_name(build_id: str, segment: str, tier: str) -> str
    """Get display name, handling special cases (FF-AIW-03)"""

def enrich_curated_build_with_ship_name(build: dict) -> dict
    """Add ship_name, ship_display_name, ship_series, ship_description"""
```

**Updated Endpoint**:
- `GET /api/public/curated-builds` - Now includes ship name fields

**Response example**:
```json
{
  "id": "FF-GVG-02",
  "segment": "Great-value Gaming",
  "tier": "Mid-range",
  "name": "Atlas Pulse",
  "display_name": "Reliant Pro",
  "ship_name": "Reliant Pro",
  "ship_display_name": "Reliant Pro",
  "ship_series": "TOS/TNG",
  "ship_description": "Reliable workhorse class ship",
  "price_gbp": 899,
  "bot_approval_queue_id": 123,
  ...
}
```

**Frontend** (FlipFlop.shop.new):

**Updated Files**:
- `lib/types.ts` - Added ship name fields to `CuratedBuild` interface
- `app/build/page.tsx` - Tier labels now "Base/Pro/Ultra"

**UI Updates Needed**:
- Display ship names prominently on build cards
- Show ship series/description as flavor text
- Use Base/Pro/Ultra in wizard tier selection
- Include ship names in performance cards
- Add ship names to spec cards
- Show ship names in registration plates

---

## 2. Listing Packs for Curated Playbooks (⏳ PENDING)

### Requirements

Each curated playbook needs ~15 images:
1. **Spec coverage images** (3-5 images)
2. **Performance images** (3-5 images)
3. **Realistic stills from 3D model** (7-10 images)

### Existing Infrastructure to Reuse

**From Personalised Website/**:
- `performance-data.json` → `index.html` rendering
- Performance card template with benchmarks
- Spec card rendering
- HTML → image conversion pipeline

**From flipflop-api/**:
- `app/api/manual_builds.py` - Listing generation
- `app/services/ebay_listing_poster.py` - eBay listing prep
- `app/services/listing_generator.py` - Listing content generation

### Implementation Plan

#### Step 1: Extend Curated Build Model

Add to `data/curated_build_definitions.json` (or new table):
```json
{
  "id": "FF-GVG-02",
  "listing_pack": {
    "performance_data": { /* Novabench, Cinebench, gaming FPS */ },
    "spec_card_data": { /* Auto-generated from components */ },
    "registration_plate_data": { /* Ship name, tier, specs */ },
    "hero_image_url": "https://...",
    "gallery_images": [...]
  }
}
```

#### Step 2: Performance Card Generation

**Create**: `app/services/curated_listing_generator.py`

```python
async def generate_performance_card_for_curated_build(
    build_id: str,
    performance_data: dict,
    output_dir: Path
) -> Path:
    """
    Generate performance card HTML and convert to images.
    
    Reuses:
    - Personalised Website/performance-data.json schema
    - Personalised Website/index.html template
    - HTML → PNG conversion (playwright/puppeteer)
    """
```

**Data structure** (same as manual builds):
```json
{
  "meta": {
    "pc_name": "Reliant Pro",
    "ship_series": "TOS/TNG",
    "tier": "Mid-range"
  },
  "benchmarks": [
    {"label": "Novabench Overall", "value": "4521", "tier": "excellent"},
    {"label": "Cinebench 2026 CPU (Multi)", "value": "18,234", "tier": "great"},
    ...
  ],
  "games": [
    {"name": "Cyberpunk 2077", "fps": "85", "preset": "Ultra", "resolution": "1440p", "stars": 4.5},
    ...
  ]
}
```

#### Step 3: Spec Card Generation

**Create**: `app/services/spec_card_generator.py`

```python
async def generate_spec_card_for_curated_build(
    build_id: str,
    components: dict,
    output_dir: Path
) -> Path:
    """
    Generate spec card HTML with ship name and components.
    
    Template includes:
    - Ship name prominently
    - Tier (Base/Pro/Ultra)
    - Component list with icons
    - Use case description
    """
```

#### Step 4: 3D Model Stills

**Prerequisites**:
- MeshyBot-generated `.glb` for each case + components
- Rendering pipeline (Blender headless / Three.js screenshot)

**Create**: `app/services/curated_model_renderer.py`

```python
async def render_3d_stills_for_curated_build(
    build_id: str,
    glb_path: Path,
    angles: list[str],  # ['front', 'side', 'three_quarter', 'top', 'detail_gpu', ...]
    output_dir: Path
) -> list[Path]:
    """
    Render realistic stills from completed 3D model.
    
    If rendering pipeline exists:
    - Reuse it directly
    
    If not:
    - Create scaffold with TODO markers
    - Document what MeshyBot provides
    - Manual upload alternative
    """
```

#### Step 5: Listing Pack Assembly

**Extend**: `app/api/public_catalogue.py`

```python
@router.get('/curated-builds/{build_id}/listing-pack')
async def get_curated_build_listing_pack(build_id: str):
    """
    Return listing pack for a curated build.
    
    Returns:
    {
      "build_id": "FF-GVG-02",
      "ship_name": "Reliant Pro",
      "images": [
        {"type": "hero", "url": "...", "alt": "Miranda Pro Hero Shot"},
        {"type": "spec_card", "url": "...", "alt": "Specifications"},
        {"type": "performance_chart", "url": "...", "alt": "Performance Benchmarks"},
        {"type": "3d_front", "url": "...", "alt": "Front View"},
        ...
      ],
      "ebay_description_html": "...",
      "storefront_description_html": "..."
    }
    """
```

---

## 3. Personalised Build Portal (⏳ PENDING)

### Requirements

Show **completed 3D model** (case filled with components) prominently.

### Existing Infrastructure

**Location**: Unclear - needs investigation

Possible locations:
- `Personalised Website/` - Performance card template
- `flipflop-admin/` - Admin build management
- `pc-flipper-customer/` - Customer portal (if exists)
- `flipflop-api/app/api/public_products.py` - Public product endpoints

### Investigation Needed

1. **Find existing personalised/owner portal**:
   - Search for customer-facing build view
   - Check if 3D viewer already exists
   - Identify where order/build details are shown to customers

2. **Locate 3D model integration**:
   - Check if MeshyBot `.glb` files are already served
   - Find Three.js / WebGL viewer code
   - Identify where components are rendered in 3D

3. **Extend, don't rebuild**:
   - Add ship name to portal
   - Ensure 3D model is prominent
   - Match visual standard of storefront build details

### Implementation Tasks

**Step 1**: Map existing customer portal
```bash
# Search for customer portal routes
grep -r "customer.*portal\|order.*view\|build.*view" --include="*.ts" --include="*.tsx"

# Find 3D viewer components
grep -r "three.*js\|webgl\|glb\|gltf" --include="*.ts" --include="*.tsx"

# Check for MeshyBot integration
grep -r "meshy.*bot\|meshy.*gen" --include="*.py"
```

**Step 2**: Integrate ship names into portal

**Step 3**: Ensure 3D model is prominent (not stubbed)

---

## 4. HTML → Image Pipeline (⏳ PENDING)

### Requirements

Reuse existing tool that converts:
- Performance HTML → performance images
- Spec HTML → spec images

### Existing Code Paths

**Investigation targets**:
- `flipflop-api/app/api/manual_builds.py` - Lines ~1257-1400 (generate_listing)
- `Personalised Website/render.js` - Performance card rendering
- `Personalised Website/render-ebay.js` - eBay listing rendering
- Look for Playwright/Puppeteer screenshot code
- Look for HTML → PNG conversion

**Known patterns**:
```python
# From manual_builds.py - evidence data structure
evidence = build.evidence_data or {}
spec_card_data = evidence.get("spec_card") or { /* auto-gen */ }
performance_card_data = evidence.get("performance_card") or _load_build_performance_evidence(build.name)
```

### Implementation Plan

**Step 1**: Find HTML → image conversion code
```bash
cd flipflop-api
grep -r "playwright\|puppeteer\|screenshot\|html.*image\|render.*html" --include="*.py"
```

**Step 2**: Extract into reusable service
```python
# app/services/html_to_image.py
async def render_html_to_image(
    html_content: str,
    output_path: Path,
    viewport: tuple[int, int] = (1200, 630)
) -> Path:
    """Generic HTML → PNG renderer using Playwright"""
```

**Step 3**: Apply to curated playbooks
```python
# Generate performance card image
perf_html = render_performance_card(performance_data)
perf_image = await render_html_to_image(perf_html, output_dir / "performance.png")

# Generate spec card image
spec_html = render_spec_card(spec_card_data)
spec_image = await render_html_to_image(spec_html, output_dir / "spec.png")
```

---

## Data Flow

```
Curated Build Definition (ship_names.json)
     ↓
Ship Naming Service
     ↓ enriches with ship names
Public API Response
     ↓
FlipFlop.shop Frontend (displays ship names)

Curated Build Definition (components + tier)
     ↓
Performance Data (benchmarks, FPS estimates)
     ↓
Performance Card Generator (HTML template)
     ↓
HTML → Image Renderer (Playwright)
     ↓
Performance Card Image

MeshyBot (.glb file for case + components)
     ↓
3D Model Renderer (Blender / Three.js)
     ↓
Multiple Angle Stills (front, side, top, detail)
     ↓
Listing Pack (15 images total)
```

---

## Files Created/Modified

### ✅ Completed (Ship Naming)

**Backend**:
- `flipflop-api/data/ship_names.json` - NEW: Configuration
- `flipflop-api/app/services/ship_naming.py` - NEW: Ship naming service
- `flipflop-api/app/api/public_catalogue.py` - MODIFIED: Add ship names to response

**Frontend**:
- `FlipFlop.shop.new/lib/types.ts` - MODIFIED: Add ship name fields
- `FlipFlop.shop.new/app/build/page.tsx` - MODIFIED: Base/Pro/Ultra labels

### ⏳ Pending (Listing Packs)

**Backend**:
- `flipflop-api/app/services/curated_listing_generator.py` - NEW: Listing pack generation
- `flipflop-api/app/services/spec_card_generator.py` - NEW: Spec card HTML
- `flipflop-api/app/services/curated_model_renderer.py` - NEW: 3D still rendering
- `flipflop-api/app/services/html_to_image.py` - NEW: HTML → PNG converter
- `flipflop-api/app/api/public_catalogue.py` - EXTEND: Add listing pack endpoint

**Data**:
- `flipflop-api/data/curated_performance_data/` - NEW: Dir for performance JSONs
- `flipflop-api/data/curated_listing_packs/` - NEW: Dir for generated images

### ⏳ Pending (Personalised Portal)

**Investigation needed**:
- Find existing customer portal codebase
- Locate 3D viewer integration
- Map MeshyBot `.glb` serving

**Then extend**:
- Add ship names to portal
- Ensure 3D model prominence
- Match storefront visual standard

---

## Testing Checklist

### Ship Naming
- [x] Configuration loads from `ship_names.json`
- [x] `get_ship_name()` returns correct name + suffix
- [x] Special case FF-AIW-03 returns "Enterprise Ultra"
- [x] API response includes ship_name fields
- [ ] Frontend displays ship names in build cards
- [ ] Wizard tier selection shows Base/Pro/Ultra
- [ ] Ship series/description shown as flavor text

### Listing Packs
- [ ] Performance data structure matches manual builds
- [ ] Performance card HTML renders correctly
- [ ] Spec card HTML includes ship name
- [ ] HTML → image conversion produces high-quality PNGs
- [ ] 3D stills rendered from `.glb` files (or scaffolded)
- [ ] Listing pack endpoint returns all 15 images
- [ ] Images suitable for eBay listing
- [ ] Images suitable for storefront gallery

### Personalised Portal
- [ ] Existing portal identified and mapped
- [ ] 3D model viewer works with curated builds
- [ ] Ship names displayed in portal
- [ ] Visual standard matches storefront
- [ ] Completed 3D model (case + components) shown prominently

---

## Next Steps

### 1. Complete Frontend Ship Name Display

- [ ] Update build cards to show ship names prominently
- [ ] Add ship series as subtitle or flavor text
- [ ] Use Base/Pro/Ultra labels consistently in UI
- [ ] Add ship name to configurator page header

### 2. Investigate Existing Code Paths

- [ ] Map performance card → image pipeline in manual builds
- [ ] Find HTML → PNG conversion code (Playwright/Puppeteer)
- [ ] Locate existing 3D viewer (if any)
- [ ] Check MeshyBot integration status

### 3. Implement Listing Pack Generation

- [ ] Create `curated_listing_generator.py` service
- [ ] Implement performance card generation
- [ ] Implement spec card generation
- [ ] Extract HTML → image renderer
- [ ] Scaffold 3D still rendering (or integrate existing)
- [ ] Create listing pack assembly endpoint

### 4. Extend Personalised Portal

- [ ] Find and document existing portal
- [ ] Add ship names to portal display
- [ ] Ensure 3D model prominence
- [ ] Match storefront visual quality

---

## Open Questions for Michael

1. **Performance Data Source**:
   - Will performance benchmarks be provided per curated playbook?
   - Or should we use typical/estimated performance for the CPU+GPU combo?
   - Novabench/Cinebench/gaming FPS - real or estimated?

2. **3D Model Stills**:
   - Does a rendering pipeline already exist?
   - If not, priority: build it or scaffold for manual upload?
   - What angles/views are most important?

3. **Personalised Portal**:
   - Where is the existing customer portal?
   - Is there already a 3D viewer integration?
   - Should curated builds use the same portal as manual builds?

4. **Ship Name Approval**:
   - Are the proposed ship names blessed?
   - Any changes needed to the mapping?
   - Prometheus stays as unique name?

---

**Status**: 🚧 **Ship Naming Complete, Listing Packs Pending Investigation**  
**Branch**: `cursor/curated-playbooks-storefront-13ea`  
**Ready for**: Frontend ship name display, existing code investigation, listing pack implementation
