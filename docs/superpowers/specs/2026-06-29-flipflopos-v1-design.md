# FlipFlopOS v1.0 Design Specification

**Status:** Design Approved  
**Version:** 1.0 (MVP)  
**Date:** 2026-06-29  

---

# Executive Summary

FlipFlopOS is a hybrid made-to-order and speculative PC building business platform. Customers configure custom PCs through a 3D configurator, or purchase pre-built "gem" builds. The system intelligently sources components, generates dynamic welcome guides, and tracks builds through completion.

**Core Workflow:**
1. Customer configures PC or browses ready-to-ship options
2. Customer pays full price upfront
3. System sources parts from vendors (or ships pre-built)
4. You build, QA, generate welcome guide
5. Ship with welcome guide PDF included

---

# Architecture

## Services

**flipflop-storefront**
- Customer-facing 3D configurator
- Budget input → spec recommendations
- Component selection with real-time pricing
- OS selection (Windows/Linux)
- Desktop theme selection (10 pre-made Rainmeter themes)
- Welcome guide preview
- Order history and build tracking dashboard
- Authentication (signup/login)

**flipflop-api**
- Quote engine (budget → specs → price)
- Sourcing engine (find vendors, get pricing)
- Build generator (LLM-powered gem suggestions)
- Order management (CRUD, status tracking)
- Welcome guide generator (PDF creation)
- License key assignment
- Payment processing integration
- Email notifications

**flipflop-admin**
- Order queue and build tracking
- Sourcing approval (vendor/price suggestions)
- QA checklist and photo uploads
- Build status management
- Welcome guide review/editing
- Gem build recommendations display
- Customer support interface

## Data Flow

```
Customer Budget Input
    ↓
Quote Engine (calculates specs based on budget)
    ↓
3D Configurator (customer customizes)
    ↓
Component Selection (CPU/GPU/RAM/SSD/PSU/Cooler/Fans/Motherboard)
    ↓
OS Selection (Windows/Linux) → License Key Assignment (if Windows)
    ↓
Theme Selection (10 Rainmeter themes)
    ↓
Final Quote (parts cost + labor + total)
    ↓
Payment (full price, upfront)
    ↓
Order Created → Sourcing begins
    ↓
Parts arrive → Build begins
    ↓
QA passes → Welcome Guide Generated (auto)
    ↓
Ready to ship → Packing and label
    ↓
Shipped → Customer notified
    ↓
Delivered → Welcome guide included
```

---

# Customer Experience

## Pre-Purchase

**Landing Page (Option C: Custom Priority)**
- Large hero: "🛠️ Build Your Perfect PC"
- Secondary: "Or browse ready-to-ship options"
- Authentication required (signup/login)

**Budget Entry**
- Slider or input: £800-£3000
- System recommends baseline spec (CPU/GPU/RAM combo)

**3D Configurator**
- Real-time 3D preview (Meshy AI models from 2D product images)
- Component browser (Motherboard, CPU, GPU, RAM DDR4/DDR5, SSD, PSU 750W, Cooler, Fans)
- Stock status indicators:
  - 🟢 In stock (ship 2 days)
  - 🟠 3-5 day lead time
  - 🔴 Unavailable
- Smart alternatives ("Want RTX 4090? Not available. Try 4080, saves £280, 3-day lead")
- Real-time price updates (left sidebar, always visible)

**OS Selection**
- Radio buttons: Windows or Linux
- If Windows: license key selection or "Need new key?"
  - Dropdown of available keys from inventory
  - Show OS version (Windows 11 Home/Pro, etc.)

**Theme Selection (Windows only)**
- 10 pre-made Rainmeter themes with preview images
- Examples: "Cyberpunk Blue", "Forest Green", "Minimalist Dark", "Gaming RGB", etc.
- Theme includes: Rainmeter skins + desktop background + widget configuration

**Review Quote**
- Component list (with images and prices per component)
- Labor cost (e.g., 3.5 hours @ £25/hr = £87.50)
- Overhead (e.g., 10% = £102)
- **Total price (bold, large)**
- Estimated build time (7-10 days for made-to-order)

**Payment**
- Stripe or PayPal integration
- Full price upfront (no deposits)
- Order confirmation email sent immediately

## Post-Purchase (Customer Dashboard)

**My Builds Page**
- List all orders (past and current)
- Per order:
  - Build thumbnail (specs: CPU/GPU/RAM summary)
  - Status badge (Sourcing / Building / QA / Shipping / Delivered)
  - Estimated delivery date (countdown)
  - Price and order ID
  - Click to expand: full specs, selected theme, OS version, license key (if applicable)

**Build Status Tracking**
- Visual timeline showing: Sourcing → Building → QA → Shipping → Delivered
- Current stage highlighted
- Status change emails:
  - "Order placed" → "We're sourcing your parts"
  - "Parts arrived" → "Your parts have arrived, build starting"
  - "QA passed" → "Your PC is ready to ship"
  - "Shipped" → "On the way! [tracking link]"
  - "Delivered" → "Your PC has arrived! [request rating]"

**Profile**
- Name, email, address, phone
- Saved payment methods
- Order history (filterable by status, date)
- Preferences (none required for v1.0, extensible for v1.1+)

---

# Data Model

## Entities

### Customer
```
id (PK)
email (unique)
password_hash
name
address
phone
created_at
last_login
```

### Order
```
id (PK)
customer_id (FK → Customer)
status (enum: sourcing, building, qa, shipping, delivered)

Specs:
- motherboard_id (FK → Inventory, component_type='motherboard')
- cpu_id (FK → Inventory)
- gpu_id (FK → Inventory)
- ram_id (FK → Inventory)
- ssd_id (FK → Inventory)
- psu_id (FK → Inventory)
- cooler_id (FK → Inventory)
- fans_id (FK → Inventory, qty)

Configuration:
- os_type (enum: windows_home, windows_pro, linux_ubuntu, linux_fedora)
- windows_license_key_id (FK → OSComponent, nullable)
- theme_id (FK → DesktopTheme, nullable)
- playbook_id (FK → Playbook, nullable) [used for speculative builds]

Pricing:
- parts_cost_total (float)
- labor_cost (float)
- overhead_cost (float)
- total_price (float)

Timing:
- created_at
- sourcing_started_at
- building_started_at
- qa_passed_at
- shipped_at
- delivered_at
- estimated_delivery_date

Notes:
- sourcing_notes (json: vendor selections, prices approved)
- build_notes (json: issues, resolutions, photos)
```

### OSComponent
```
id (PK)
os_type (enum: windows_home, windows_pro, windows_enterprise, linux_ubuntu, linux_fedora)
license_key (string, encrypted)
assigned_to_order_id (FK → Order, nullable)
purchased_cost (float)
resale_price (float)
status (enum: available, assigned, used)
created_at
assigned_at
```

### Playbook (Enhanced)
```
id (PK)
name (e.g., "1080p Gaming", "4K Workstation")
target_budget (float)
target_use_case (string)
recommended_specs (json: cpu_model, gpu_model, ram_gb, etc.)

NEW FIELDS:
- ninite_software_list (json array)
  [
    "Google Chrome",
    "VLC Media Player",
    "Discord",
    "OBS Studio",
    "Blender" (if workstation),
    ...
  ]

created_at
updated_at
```

### DesktopTheme
```
id (PK)
name (e.g., "Cyberpunk Blue", "Forest Green")
rainmeter_config_path (string)
desktop_background_path (string)
preview_image_path (string)
description (text)
created_at
```

### WelcomeGuide
```
id (PK)
order_id (FK → Order, unique)
pdf_blob (binary, stored in DB or S3)
generated_at
content_json (json)
  {
    "component_overview": {...},
    "bios_settings": [...],
    "windows_license_key": "...",
    "pre_installed_software": [...],
    "theme_walkthrough": {...},
    "first_boot_steps": [...],
    "troubleshooting": [...]
  }
```

### Component (existing inventory, simplified for v1.0)
```
id (PK)
component_type (enum: motherboard, cpu, gpu, ram, ssd, psu, cooler, fans, case)
product_name (string)
vendor (string)
condition (enum: new, open_box, refurbished)
price (float)
model_number (string)
stock_qty (int)
lead_time_days (int)
purchase_cost (float)
created_at
updated_at
```

---

# Build Process (Operator Workflow)

## Order Received

```
1. ORDER PLACED
   Status: sourcing
   Customer email: "Thank you! We're sourcing your parts. Estimated build time: 7-10 days."
   Admin sees: Order in queue, specs, customer address

2. SOURCING STAGE
   - Sourcing engine queries vendors for:
     • Motherboard
     • CPU
     • GPU
     • RAM
     • SSD
     • PSU 750W Gold
     • CPU Cooler
     • ARGB Fans
   - Summary table provided to admin: (vendor, condition, price, model, lead_time)
   - You approve best vendor combination
   - System places orders automatically or sends you purchase links
   
   Waiting for parts...
   (Auto-update when shipment tracking shows delivered)
   
   Status: building (triggered when all parts marked "received")
   Customer email: "Your parts have arrived! We're starting the build."

3. BUILD STAGE
   - Follow build checklist:
     ✓ Install CPU
     ✓ Install RAM
     ✓ Install SSD
     ✓ Install PSU
     ✓ Install motherboard in case
     ✓ Cable management
     ✓ Fans and cooler
     ✓ Thermal paste applied
     ✓ Power test
   - Upload photos at key milestones
   - Build time tracking: estimated vs actual

4. QA STAGE
   - Run QA checklist:
     ✓ POST (Power-On Self Test)
     ✓ GPU benchmark (temp, performance)
     ✓ RAM test (MemTest86 or similar)
     ✓ SSD speed test
     ✓ Thermals under load (CPU, GPU)
     ✓ Boot speed test
     ✓ Windows/Linux boot and login
     ✓ All USB ports test
   - Log any issues
   
   **IF QA PASSES:**
     ↓
     WELCOME GUIDE GENERATOR (Automatic)
     
     Input data gathered:
     - Exact component specs from Order
     - OS type and license key (if Windows)
     - Selected theme (if Windows)
     - Playbook's Ninite software list
     - System configuration (RAM speed, SSD TRIM, etc.)
     
     PDF generated with sections:
     1. **Component Overview** (specs, model numbers, warranty info)
     2. **First Boot Steps** (BIOS settings explained, drivers, Windows update)
     3. **BIOS Settings Guide** (XMP profile for RAM, GPU fans, boot order, etc.)
     4. **Windows License Key** (if applicable, clearly displayed)
     5. **Pre-installed Software** (what comes with your PC, from Ninite list)
     6. **Theme Walkthrough** (how to use Rainmeter, customize theme)
     7. **Performance Tips** (optimize for gaming, workstation, etc.)
     8. **Troubleshooting** (common issues, how to reset BIOS, factory reset, etc.)
     9. **Support & Warranty** (contact info, warranty coverage, return policy)
     
     PDF saved to:
     - Database (WelcomeGuide.pdf_blob)
     - Order artifacts (filesystem)
     
     Status: ready_to_ship
     Customer email: "Your PC passed QA! We're packing and shipping tomorrow."
   
   **IF QA FAILS:**
     - Log failure reason
     - Repair or replace component
     - Re-run QA
     - Do NOT generate guide until QA passes

5. PACKING STAGE
   - Pack PC with care (foam, cable management visible)
   - Include:
     • All cables and manuals
     • Windows license key card (if Windows)
     • Welcome guide PDF (printed or digital)
     • Thank you note
   - Get shipping label (dimensions/weight)

6. SHIPPING STAGE
   Status: shipped
   estimated_delivery_date calculated (today + carrier time)
   Customer email: "Your PC is on the way! Tracking: [link]"
   Tracking link provided in email

7. COMPLETION
   Status: delivered
   Customer email: "Your PC has arrived! Please leave a rating."
   Request rating/feedback (1-5 stars + comment)
```

---

# LLM Build Generator (Continuous, Admin Tool)

## Automated Gem Build Recommendations

**Trigger:** Whenever component catalogues update (new products, discontinued, price changes)

**Process:**

```
1. CATALOGUE CHANGE DETECTED
   - New GPU added?
   - PSU price dropped 20%?
   - CPU discontinued?

2. LLM BUILD GENERATOR RUNS
   Input data:
   - Current component inventory (name, vendor, condition, price, model, lead_time)
   - Live eBay market prices (new and used for each component)
   - Demand trends (what customers are configuring most)
   - Playbook definitions (use case, budget targets)
   
   LLM analysis:
   - What high-profit combinations are possible?
   - What specs match current demand?
   - What has the best margin?
   - What sells fastest (based on historical data)?

3. OUTPUT: Gem Build Recommendations
   Per build:
   - Name ("RTX 4070 Gaming PC")
   - CPU
   - GPU
   - RAM (DDR4 or DDR5)
   - SSD
   - PSU
   - Cooler
   - Fans
   - Case
   - Cost breakdown (parts sum)
   - Suggested retail price
   - Margin (%)
   - Market comparable (eBay listings with similar specs, current prices)
   - Demand signal (e.g., "high demand for 1440p gaming")
   - Estimated build time (hours)

4. ADMIN SEES:
   Gem builds dashboard:
   - Green badge: "NEW" (not built yet)
   - Yellow badge: "REFRESH" (existing build, updated prices/specs)
   - Red badge: "RETIRE" (no longer profitable/relevant)
   
   Per recommendation:
   - Build name
   - Cost → Retail price
   - Margin %
   - Why (demand signal)
   - Action buttons: "Build this", "Remind later", "Skip"

5. YOU DECIDE:
   "Build this gem" → creates a speculative build order
   - Auto-assigns to a pre-defined playbook
   - Follows normal build process
   - Once QA passes, appears on storefront as "Ready-to-Ship"
   - Fast delivery (2-3 days)
```

---

# Playbook Enhancement

**New field: ninite_software_list**

```json
{
  "name": "1080p Gaming",
  "target_budget": 1200,
  "target_use_case": "gaming",
  "recommended_specs": {...},
  
  "ninite_software_list": [
    "Google Chrome",
    "Discord",
    "Steam",
    "OBS Studio",
    "VLC Media Player",
    "7-Zip",
    "GeForce Experience" (GPU-specific)
  ]
}
```

During welcome guide generation, this list is included in the "Pre-installed Software" section. Implementation via Ninite (v1.1+) or manual note (v1.0).

---

# Design System & UI Style Guide

**Framework:** Claude Design System (CDS)  
**Aesthetic Direction:** Premium luxury (Porsche configurator experience)

## Premium Aesthetic Principles

- **Minimalism:** Generous whitespace, single focal point per screen
- **Typography:** Large, confident, elegant (serif for hero statements, sans-serif for UI)
- **Material Depth:** Subtle shadows, high contrast, no gloss or gradients
- **Animation:** Smooth, deliberate, satisfying (100-200ms transitions)
- **Micro-interactions:** Every click gets feedback (ripple, color shift, subtle scale)
- **Photography/3D:** Professional quality, high resolution, fast rendering
- **Pricing:** Always visible, never hidden, premium font treatment
- **Status:** Color-coded, intuitive, never ambiguous

## Color Palette (Premium)

- **Primary CTA:** Deep charcoal or navy (not bright blue)
  - Usage: "Configure Now", "Complete Order", "Finalize"
  - Hover: 5% lighter shade (smooth transition)
- **Success:** Soft sage green (muted, professional)
- **Warning/Lead Time:** Warm champagne gold or muted amber
- **Error/Unavailable:** Deep burgundy (not bright red)
- **Text Primary:** Near-black (#1a1a1a) or ivory (#f5f5f0)
- **Text Secondary:** Warm gray (#777777)
- **Surfaces:** Off-white (#faf9f8) or charcoal (#1f1f1f) in dark mode
- **Borders:** Hairline, barely visible, only for structure
- **Accent Highlight:** Warm gold or copper (for premium touches)

## Stock Status Indicators

- 🟢 In stock: `color: var(--text-success); font-weight: 500;`
- 🟠 Lead time: `color: var(--text-warning); font-weight: 500;`
- 🔴 Unavailable: `color: var(--text-danger); font-weight: 500;`

## Button Styles

- **Primary CTA:** `background: var(--fill-accent); color: var(--on-accent); padding: 12px 24px;`
  - Usage: "Complete Order", "Start Build"
- **Secondary:** `background: transparent; border: 1px solid var(--border-strong);`
  - Usage: "Skip", "Browse alternatives"
- **Disabled:** `opacity: 0.5; cursor: not-allowed;`
  - Usage: "Next" button on incomplete form

## 3D Configurator Viewport (Hero Experience)

- **Size:** Full width, 60-70% of screen (dominant focal point)
- **Appearance:** Borderless or subtle frame (1px hairline)
- **Background:** Smooth gradient (off-white to light gray) or solid premium color
- **Lighting:** Studio lighting (key light + fill light) for dramatic, luxurious appearance
- **Models:** Smooth, reflective materials; realistic component finishes (brushed aluminum, RGB lighting)
- **Interaction:** Smooth rotation (mouse drag), zoom (scroll), light rotation on hover
- **Performance:** Load in <2s, 60fps interactions
- **Loading State:** Elegant spinner with "Configuring your PC..." message (not a default loader)

## Homepage Hero (Porsche Aesthetic)

- **Hero Statement:** "🛠️ Build Your Perfect PC"
  - Large, confident typography (48-56px)
  - Serif or premium sans-serif
  - Single line focus
  - Paired with 1-2 line description: "Configure to your specs. 3D preview. Built in 7 days."
  
- **Visual:** 3D model of a high-end gaming PC (beautiful lighting, rotating slowly on autoplay)
- **CTA:** Single prominent button below ("Start Configuring") in premium accent color
- **Secondary Option:** Below fold: "Or browse ready-to-ship" (smaller, subtle)

## Typography

- **Heading (h1):** 48px, font-weight: 500, serif (premium feel)
- **Heading (h2):** 32px, font-weight: 400, serif or elegant sans
- **Heading (h3):** 20px, font-weight: 500
- **Body text:** 16px, font-weight: 400, line-height: 1.8 (generous)
- **Labels:** 12px, font-weight: 500, all-caps only for micro-labels (rare)
- **Price display:** 24px, font-weight: 600, warm gold color, no currency symbol prefix (just "1,299" not "$1,299")

## Dark Mode

- Automatic via CDS (no manual overrides needed)
- All surfaces, text, borders adapt via CSS variables
- No hardcoded colors (use `var(--*)` throughout)

## Accessibility

- WCAG AA contrast on all text
- Focus rings on all interactive elements
- Semantic HTML (buttons, links, form elements)
- Alt text on all 3D model images and component photos
- Keyboard navigation (tab order, arrow keys for selections)

---

# Implementation Roadmap

## v1.0 (MVP, 6-8 weeks)

- Storefront with 3D configurator
- Budget → quote flow
- Component selection with stock indicators
- OS selection (Windows/Linux)
- Windows license key assignment
- Desktop theme selection (10 themes, preview)
- Authentication (signup/login)
- Payment integration (Stripe)
- Order creation and management
- Build tracking dashboard
- Build process checklist (sourcing, building, QA)
- Welcome guide PDF generation (auto on QA pass)
- Email notifications on status change
- Admin dashboard with order queue
- Sourcing approval UI
- LLM build generator (continuous, recommendations only)

## v1.1 (Post-launch, 2-3 weeks)

- Ninite integration (auto-install software lists)
- Advanced customer preferences (saved builds, favorites)
- Build templates (pre-configured specs by use case)

## v1.2+ (Future)

- Ancillary revenue (software key reselling, Adobe subscriptions)
- Advanced analytics (profit per build type, customer lifetime value)
- Multi-location support
- Team assignments (if scaling)

---

# Success Criteria

**Customer:**
- Can order custom PC in < 5 minutes
- Sees real-time pricing and stock status
- Receives order updates via email
- Can track build progress
- Receives welcome guide with PC

**Business:**
- Zero inventory risk on made-to-order (customer pays upfront)
- Gem builds generated by demand, not speculation
- Welcome guides increase customer satisfaction (reduces returns)
- Desktop themes = differentiation from competitors
- Email engagement tracks build progress (repeat customers)

---

# Open Questions / Future Considerations

- Should customers be able to request quotes without paying (v1.1)?
- Should we offer build financing (buy now, pay later)? (v1.2)
- Should we support international shipping? (v1.1)
- Should we track component warranty dates? (v1.1)
- Should customers be able to schedule delivery dates? (v1.1)

---

# Appendix: Example Welcome Guide Sections

**Component Overview**
```
Your PC Build: "RTX 4070 Gaming"

Components:
- Motherboard: MSI MAG B850 EDGE WiFi (Socket AM5)
- CPU: AMD Ryzen 7 5800X3D (8-core, 4.2GHz base)
- GPU: NVIDIA RTX 4070 12GB GDDR6X
- RAM: Corsair Vengeance DDR5 32GB 6000MHz CAS 30
- SSD: Samsung 990 Pro 2TB NVMe
- PSU: Corsair RM850x 850W (80+ Gold)
- Cooler: Noctua NH-D15 chromax
- Case: NZXT H7 Flow RGB
- Warranty: 3 years (parts), 1 year (labor)
```

**BIOS Settings**
```
1. Enable XMP Profile for RAM
   - Restart PC → press Del during boot → enter BIOS
   - Navigate to: Overclocking → OC Profiles
   - Select "Profile 1" (optimized for your RAM)
   - Save and exit
   
2. GPU PCIe Slot Settings (optional)
   - BIOS → PCIe Configuration
   - Set PCIe x16 slot to "PCIe Gen 4" (for RTX 4070)
   
3. Storage Boot Order
   - BIOS → Boot → Boot Device Priority
   - Set NVMe (Samsung 990 Pro) as first boot device
```

**Troubleshooting**
```
PC won't turn on:
1. Check power cable connection
2. Press power button for 10 seconds (hard reset)
3. Try a different outlet
4. Contact support: [email]

PC runs slow:
1. Check Task Manager (Ctrl+Shift+Esc)
   - Are any programs using 100% CPU/disk?
2. Run Windows Update (Settings → Update & Security)
3. Check SSD space (should have > 10% free)

High temperatures:
1. Clean case fans (dust reduces cooling)
2. Verify CPU cooler is seated properly
3. Check BIOS → CPU fan speed curve (should ramp up under load)
```

