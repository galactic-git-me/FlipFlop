# Shared Card Services Architecture

**Status**: 🏗️ Architecture Defined | ⏳ Implementation Pending  
**Branch**: `cursor/curated-playbooks-storefront-13ea`  
**PR**: [#12](https://github.com/galactic-git-me/FlipFlop/pull/12)

## Overview

Refactor existing pre-built card tooling into **3 reusable services** shared by BOTH pre-builts and curated playbooks, following Michael's confirmed architecture.

---

## Ship Names (LOCKED ✅)

| Customer Type | Ship Name | Budget | Mid-range | High-end |
|---------------|-----------|--------|-----------|----------|
| Great-value Gaming | **Reliant** | Reliant | Reliant Pro | Reliant Ultra |
| High-performance Gaming | **Defiant** | Defiant | Defiant Pro | Defiant Ultra |
| Student Hybrid | **Voyager** | Voyager | Voyager Pro | Voyager Ultra |
| Business & Office | **Excelsior** | Excelsior | Excelsior Pro | Excelsior Ultra |
| Content Creation | **Galaxy** | Galaxy | Galaxy Pro | Galaxy Ultra |
| AI Workstation | **Enterprise** | Enterprise | Enterprise Pro | Enterprise Ultra |
| Software Development | **Titan** | Titan | Titan Pro | Titan Ultra |
| Family & Home | **Stargazer** | Stargazer | Stargazer Pro | Stargazer Ultra |

**PUBLIC DISPLAY PATTERN**:
- Budget → `{Ship}` (e.g., "Reliant")
- Mid-range → `{Ship} Pro` (e.g., "Reliant Pro")
- High-end → `{Ship} Ultra` (e.g., "Reliant Ultra")

**⚠️ DO NOT use "Base"** - Budget tier is just the ship name without suffix

**Special case**: FF-AIW-03 (AI Workstation High) = "Enterprise Ultra" (bespoke/consult only)

---

## Three Shared Card Services

### 1. Performance Card Service

**Input**: `performance.json`  
**Output**: Performance card HTML → images

**Data structure** (reuses `Personalised Website/performance-data.json` schema):
```json
{
  "meta": {
    "build_id": "FF-GVG-02",
    "pc_name": "Atlas Pulse",
    "ship_name": "Reliant Pro",
    "config_hash": "a3f5b2c8d1e9f7a2",
    "generated_at": "2026-09-21T10:48:00Z"
  },
  "benchmarks": [
    {"label": "Novabench Overall", "value": "4521", "tier": "excellent"},
    {"label": "Cinebench 2026 CPU (Multi)", "value": "18,234", "tier": "great"}
  ],
  "games": [
    {"name": "Cyberpunk 2077", "fps": "85", "preset": "Ultra", "resolution": "1440p", "stars": 4.5}
  ],
  "specs": [
    {"label": "CPU", "value": "AMD Ryzen 5 9600X", "icon": "cpu"},
    {"label": "GPU", "value": "AMD Radeon RX 9060 XT 16GB", "icon": "gpu"}
  ]
}
```

**Template**: Reuse `Personalised Website/index.html`  
**Rendering**: HTML template + JSON → Full HTML page  
**Conversion**: Playwright screenshot → PNG images (multiple sizes)

**Used by**:
- Pre-builts (manual builds)
- Curated playbooks (standard BOM)
- Post-purchase (as-bought BOM with upsells)

### 2. Spec Card Service

**Input**: `build.json`  
**Output**: Spec card HTML → images

**Data structure**:
```json
{
  "meta": {
    "build_id": "FF-GVG-02",
    "pc_name": "Atlas Pulse",
    "ship_name": "Reliant Pro",
    "tier": "Mid-range",
    "config_hash": "a3f5b2c8d1e9f7a2",
    "generated_at": "2026-09-21T10:48:00Z"
  },
  "components": [
    {"slot": "cpu", "name": "AMD Ryzen 5 9600X"},
    {"slot": "gpu", "name": "AMD Radeon RX 9060 XT 16GB"},
    {"slot": "ram", "name": "32GB (2x16GB) DDR5-6000 CL30"},
    {"slot": "storage", "name": "2TB PCIe 4.0 NVMe SSD"},
    {"slot": "case", "name": "Montech SKY TWO GX"},
    {"slot": "psu", "name": "Corsair RM750e 750W 80+ Gold"},
    {"slot": "cooling", "name": "Thermalright Peerless Assassin 120 SE"},
    {"slot": "motherboard", "name": "ASRock B850 Steel Legend WiFi"},
    {"slot": "os", "name": "Windows 11 Home"}
  ]
}
```

**Template**: New spec card HTML template  
**Features**:
- Ship name prominently displayed
- Tier badge (Base/Pro/Ultra)
- Component list with icons
- Use case description

**Used by**:
- Pre-builts
- Curated playbooks
- Post-purchase (reflects purchased components)

### 3. Registration Card Service

**Input**: Build metadata  
**Output**: Registration card/plate image

**Data structure**:
```json
{
  "meta": {
    "build_id": "FF-GVG-02",
    "pc_name": "Atlas Pulse",
    "ship_name": "Reliant Pro",
    "tier": "Mid-range",
    "config_hash": "a3f5b2c8d1e9f7a2",
    "generated_at": "2026-09-21T10:48:00Z"
  },
  "registration": {
    "ship_name": "Reliant Pro",
    "registry": "FF-GVG-02",
    "tier": "Mid-range",
    "key_specs": [
      ["CPU", "AMD Ryzen 5 9600X"],
      ["GPU", "AMD Radeon RX 9060 XT 16GB"],
      ["RAM", "32GB DDR5"],
      ["Storage", "2TB NVMe"]
    ]
  }
}
```

**Output**: Single registration plate image (like a car registration plate)  
**Style**: Star Trek aesthetic with ship name, registry number (build ID), tier

**Used by**:
- Pre-builts
- Curated playbooks
- Post-purchase

---

## Two-Phase Generation

### Phase 1: Pre-Generation (Catalogue/Site)

**When**: Build definition created / playbook published  
**BOM**: Standard recommended configuration  
**Purpose**: Marketing materials, storefront, eBay listings, indirect channels

**Process**:
1. Take recommended BOM from curated build definition
2. Generate all 3 cards with standard components
3. Compute `config_hash` = hash(components)
4. Store cards in: `/cards/{build_id}/pre_generation/{config_hash}/`
5. Use these cards for all catalogue/marketing materials

**Example**:
- FF-GVG-02 (Reliant Pro) with default 32GB RAM, 2TB storage
- config_hash: `a3f5b2c8`
- Cards stored at: `/cards/FF-GVG-02/pre_generation/a3f5b2c8/`

### Phase 2: Post-Purchase (Personalised Portal)

**When**: Order placed with component selections  
**BOM**: As-bought configuration (including upsells)  
**Purpose**: Customer's personalised build site

**Process**:
1. Customer selects upsells during checkout (e.g., 64GB RAM, 4TB storage)
2. Order stores as-bought BOM + config_hash
3. After purchase, regenerate all 3 cards with **as-bought components**
4. Store cards in: `/cards/{build_id}/post_purchase/{config_hash}/`
5. Personalised portal serves these cards (showing what customer actually bought)

**Example**:
- Customer orders FF-GVG-02 (Reliant Pro) with 64GB RAM upgrade
- New config_hash: `f7d4e1a9` (different from catalogue)
- Cards regenerated at: `/cards/FF-GVG-02/post_purchase/f7d4e1a9/`
- Customer's portal shows their specific configuration

### Config Hash Tying

**Purpose**: Tie catalogue SKU "looks" to as-bought "books/portal"

```python
def compute_config_hash(components: dict) -> str:
    """SHA256 hash of component configuration (first 16 chars)"""
    normalized = json.dumps(components, sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]
```

**On Order**:
```json
{
  "order_id": 12345,
  "curated_build_id": "FF-GVG-02",
  "ship_name": "Reliant Pro",
  "catalogue_config_hash": "a3f5b2c8",  // What they saw in catalogue
  "purchased_config_hash": "f7d4e1a9",  // What they actually bought
  "purchased_components": {
    "cpu": "AMD Ryzen 5 9600X",
    "ram": "64GB (2x32GB) DDR5-6000 CL30",  // Upgraded from 32GB
    "storage": "4TB PCIe 4.0 NVMe SSD",     // Upgraded from 2TB
    ...
  }
}
```

**Personalised portal URL**: `/builds/{order_id}` → serves cards with `purchased_config_hash`

---

## Implementation Architecture

### Core Service Module

**File**: `flipflop-api/app/services/card_services.py`

**Classes**:
1. `PerformanceCardGenerator` - performance.json → HTML → images
2. `SpecCardGenerator` - build.json → HTML → images
3. `RegistrationCardGenerator` - metadata → registration plate image
4. `CardOrchestrator` - Coordinates all 3 generators

**Helper**:
- `compute_config_hash(components)` - Stable hash for configuration

### Integration Points

#### For Pre-Builts (Manual Builds)

**Current**: `flipflop-api/app/api/manual_builds.py`

**Refactor**:
```python
from app.services.card_services import CardOrchestrator

@router.post("/{build_id}/generate-cards")
async def generate_cards_for_manual_build(build_id: int):
    """Generate all 3 cards for a manual build"""
    build = await get_manual_build(build_id, db)
    
    orchestrator = CardOrchestrator(output_base_dir=Path("/data/cards"))
    
    results = await orchestrator.generate_all_cards(
        build_id=f"MB-{build.id}",
        pc_name=build.name,
        ship_name=None,  # Pre-builts don't use ship names
        components=build.components,
        tier=None,
        performance_data=build.evidence_data.get("performance_card"),
        phase="pre_generation"
    )
    
    return results
```

#### For Curated Playbooks

**New**: `flipflop-api/app/api/curated_builds.py`

```python
from app.services.card_services import CardOrchestrator
from app.services.ship_naming import get_ship_name

@router.post("/curated-builds/{build_id}/generate-cards")
async def generate_cards_for_curated_build(build_id: str):
    """Generate all 3 cards for a curated playbook (pre-generation phase)"""
    build = get_curated_build_definition(build_id)
    ship_name = get_ship_name(build["segment"], build["tier"])
    
    orchestrator = CardOrchestrator(output_base_dir=Path("/data/cards"))
    
    results = await orchestrator.generate_all_cards(
        build_id=build_id,
        pc_name=build["name"],
        ship_name=ship_name,
        components=build["components"],
        tier=build["tier"],
        performance_data=load_curated_performance_data(build_id),
        phase="pre_generation"
    )
    
    return results
```

#### Post-Purchase Regeneration

**Trigger**: After order placed and payment confirmed

```python
@router.post("/orders/{order_id}/regenerate-cards")
async def regenerate_cards_for_order(order_id: int):
    """Regenerate cards with as-bought BOM after purchase"""
    order = await get_order(order_id, db)
    
    # Get as-bought components (including upsells)
    purchased_components = order.purchased_components
    config_hash = compute_config_hash(purchased_components)
    
    # Store hashes on order
    order.catalogue_config_hash = order.curated_build_config_hash  # Original
    order.purchased_config_hash = config_hash  # As-bought
    
    orchestrator = CardOrchestrator(output_base_dir=Path("/data/cards"))
    
    results = await orchestrator.generate_all_cards(
        build_id=order.curated_build_id,
        pc_name=order.curated_build_name,
        ship_name=order.ship_name,
        components=purchased_components,
        tier=order.curated_build_tier,
        performance_data=None,  # Reuse pre-gen performance or regenerate
        phase="post_purchase"
    )
    
    # Update order with card URLs
    order.personalised_portal_cards = results
    await db.commit()
    
    return results
```

---

## HTML → Image Conversion

### Using Playwright

**Install**: `pip install playwright` + `playwright install chromium`

**Implementation** (in `card_services.py`):

```python
from playwright.async_api import async_playwright

async def convert_html_to_images(
    html_content: str,
    output_dir: Path,
    viewports: list[tuple[str, int, int]]
) -> list[Path]:
    """
    Convert HTML to images using Playwright.
    
    Args:
        html_content: Full HTML string
        output_dir: Directory to save images
        viewports: List of (name, width, height)
    
    Returns:
        List of generated image paths
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        
        await page.set_content(html_content, wait_until="networkidle")
        
        images = []
        for name, width, height in viewports:
            await page.set_viewport_size({"width": width, "height": height})
            
            output_path = output_dir / f"{name}.png"
            await page.screenshot(path=output_path, full_page=True)
            images.append(output_path)
        
        await browser.close()
    
    return images
```

---

## File Structure

```
flipflop-api/
├── app/services/
│   ├── card_services.py          # NEW: Shared card generators
│   └── ship_naming.py             # Existing: Ship name logic
├── data/
│   ├── ship_names.json            # Ship name configuration
│   ├── cards/                     # NEW: Generated cards
│   │   ├── FF-GVG-02/
│   │   │   ├── pre_generation/
│   │   │   │   └── a3f5b2c8/      # Standard BOM
│   │   │   │       ├── performance-data.json
│   │   │   │       ├── performance-desktop.png
│   │   │   │       ├── spec-data.json
│   │   │   │       ├── spec-card.png
│   │   │   │       ├── registration-data.json
│   │   │   │       └── registration.png
│   │   │   └── post_purchase/
│   │   │       └── f7d4e1a9/      # With 64GB RAM upsell
│   │   │           └── [same files, different components]
│   │   └── [other build IDs...]
│   └── curated_performance_data/  # NEW: Performance benchmarks
│       ├── FF-GVG-02.json
│       └── [other playbooks...]
└── templates/
    ├── performance_card.html      # Reuse from Personalised Website
    ├── spec_card.html             # NEW: Spec card template
    └── registration_card.html     # NEW: Registration template
```

---

## Upsell Handling

### On Playbook Definition

**Allowed upsells** belong to the playbook:

```json
{
  "id": "FF-GVG-02",
  "name": "Atlas Pulse",
  "ship_name": "Reliant Pro",
  "components": {
    "ram": "32GB (2x16GB) DDR5-6000 CL30"
  },
  "allowed_upsells": {
    "ram": [
      {"capacity_gb": 32, "price_delta": 0, "name": "32GB (2x16GB) DDR5-6000 CL30"},
      {"capacity_gb": 64, "price_delta": 80, "name": "64GB (2x32GB) DDR5-6000 CL30"},
      {"capacity_gb": 96, "price_delta": 150, "name": "96GB (2x48GB) DDR5-6000 CL30"}
    ],
    "storage": [
      {"capacity_gb": 2000, "price_delta": 0, "name": "2TB PCIe 4.0 NVMe SSD"},
      {"capacity_gb": 4000, "price_delta": 120, "name": "4TB PCIe 4.0 NVMe SSD"}
    ]
  }
}
```

### On Order

Customer selections stored:

```json
{
  "order_id": 12345,
  "curated_build_id": "FF-GVG-02",
  "selected_upsells": {
    "ram": {"capacity_gb": 64, "price_delta": 80},
    "storage": {"capacity_gb": 4000, "price_delta": 120}
  },
  "purchased_components": {
    "cpu": "AMD Ryzen 5 9600X",
    "ram": "64GB (2x32GB) DDR5-6000 CL30",  // Upgraded
    "storage": "4TB PCIe 4.0 NVMe SSD",     // Upgraded
    ...
  },
  "total_price": 899 + 80 + 120,  // Base + upsell deltas
  "purchased_config_hash": "f7d4e1a9"
}
```

### On Personalised Portal

Portal serves cards matching `purchased_config_hash`:

```
GET /builds/{order_id}
→ Returns cards from /cards/FF-GVG-02/post_purchase/f7d4e1a9/

Spec card shows: "64GB (2x32GB) DDR5-6000" (not the catalogue's 32GB)
Performance card: May reuse pre-gen or note "upgraded configuration"
Registration card: Shows ship name + as-bought specs
```

---

## Investigation Targets

### 1. Existing Performance Card Code

**Location**: `Personalised Website/`

**Files to extract**:
- `index.html` - Performance card template
- `render.js` - JSON → DOM rendering logic
- `performance-data.json` - Schema (already documented)

**Action**: Move template to `flipflop-api/templates/`, adapt render logic to server-side

### 2. Existing Manual Build Card Generation

**Location**: `flipflop-api/app/api/manual_builds.py`

**Lines ~1280-1295**: Evidence data structure
```python
evidence = build.evidence_data or {}
spec_card_data = evidence.get("spec_card") or { ... }
performance_card_data = evidence.get("performance_card") or _load_build_performance_evidence(build.name)
```

**Action**: Refactor to use new `CardOrchestrator`

### 3. HTML → PNG Conversion

**Search for**:
- Playwright usage: `grep -r "playwright" --include="*.py"`
- Puppeteer usage: `grep -r "puppeteer" --include="*.py"`
- Screenshot code: `grep -r "screenshot" --include="*.py"`

**If not found**: Implement fresh using Playwright

### 4. Personalised Portal Location

**Search for**:
- Customer portal routes
- Order view pages
- Build detail pages for customers

**Action**: Extend to serve post-purchase cards with purchased_config_hash

---

## Testing Strategy

### Unit Tests

- [ ] `compute_config_hash()` produces stable hashes
- [ ] Same components → same hash
- [ ] Different components → different hash
- [ ] Hash survives JSON serialization changes

### Integration Tests

- [ ] Generate cards for curated build (pre-generation)
- [ ] Generate cards for manual build (pre-generation)
- [ ] Regenerate cards after upsell (post-purchase)
- [ ] config_hash matches between phases

### End-to-End Tests

- [ ] Customer views catalogue (sees pre-gen cards)
- [ ] Customer selects upsells
- [ ] Order placed with purchased_config_hash
- [ ] Cards regenerated post-purchase
- [ ] Personalised portal shows as-bought cards

---

## Migration Plan

### Phase 1: Extract & Refactor (Current)
- [x] Create `card_services.py` with architecture
- [ ] Extract performance card template from Personalised Website
- [ ] Extract spec card logic from manual builds
- [ ] Implement HTML → PNG conversion (Playwright)
- [ ] Create registration card template/generator

### Phase 2: Integrate Pre-Builts
- [ ] Refactor `manual_builds.py` to use CardOrchestrator
- [ ] Migrate existing evidence_data to new card structure
- [ ] Test with existing manual builds

### Phase 3: Integrate Curated Playbooks
- [ ] Add curated performance data (benchmarks/FPS)
- [ ] Generate pre-generation cards for all 24 playbooks
- [ ] Expose listing pack API endpoint
- [ ] Wire into storefront

### Phase 4: Post-Purchase Flow
- [ ] Add config_hash fields to Order model
- [ ] Implement post-purchase card regeneration
- [ ] Update personalised portal to serve purchased cards
- [ ] Test upsell → regeneration flow

---

**Status**: 🏗️ **Architecture Complete, Implementation Pending**  
**Next**: Extract existing templates, implement Playwright conversion, refactor manual builds  
**Ready for**: Investigation of existing code paths, template extraction, shared service implementation
