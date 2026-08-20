# 3D Case Model Sourcing Guide

## Overview
You have **226 unique PC cases** in the database. To launch the customer builder, you need **20-30 cases with 3D models**, prioritized by **Amazon bestseller rank** (most popular first).

**Target:** Top 30 bestsellers + Geometry Green case

## Target Deliverables (4 items)

You won't find all 6 sources for every case. **Aim for these 4 core deliverables:**

1. **Beautiful 3D Model** (lifelike, fully textured)
   - Preferred: Manufacturer CAD (if available)
   - Fallback: High-quality community model (Sketchfab/GrabCAD)
   - Acceptable: Hand-modeled from detailed photos if no CAD exists

2. **Product Photo Set** (multi-angle, professional quality)
   - Preferred: Official manufacturer specs/gallery photos
   - Fallback: Official Amazon listing photos
   - Angles: Front, back, interior, rear I/O ports, special features

3. **YouTube Product Video** (official showcase)
   - Preferred: Official manufacturer channel
   - Fallback: High-quality review (Linus Tech Tips, GamersNexus, JayzTwoCents)
   - Purpose: Show the case from all angles, highlight features, demonstrate interior space

4. **Description + Key Selling Points** (marketing copy)
   - 2-3 sentences highlighting what makes this case special
   - Form factors, cooling capability, design philosophy
   - Use in customer builder & pre-built listings

---

## Sourcing Priority (in order)

### 1. **Manufacturer CAD/3D Model** ⭐ BEST
- Most accurate, fully textured, ready to use
- Search: `"{Case Name} CAD"` or `"{Case Name} 3D model"`
- Check manufacturer website:
  - `/downloads` or `/resources`
  - `/technical-specifications`
  - `/support` → downloads section
  - Product page → "Technical specs" or "CAD files"
- File formats: `.step`, `.iges`, `.igs`, `.fbx`, `.obj`, `.blend`, `.3ds`

**Where to check by brand:**
- **NZXT:** nzxt.com → Products → Downloads
- **Corsair:** corsair.com → Support → Downloads
- **LIAN LI:** lian-li.com → Support → Downloads
- **Fractal Design:** fractal-design.com → Products → Files
- **Thermaltake:** thermaltakeusa.com → Support
- **Be Quiet!:** be-quiet.com → Support
- **Phanteks:** phanteks.com → Support
- **Cooler Master:** coolermaster.com → Support

---

### 1B. **Third-Party CAD/3D Models** (if manufacturer CAD unavailable)
- Community-uploaded, free, often very detailed
- Prefer **Creative Commons Licensed** (reusable for your project)

**Top sources:**
- **Sketchfab** https://sketchfab.com
  - Search: `{Case Name}` + filter by "Downloadable" + license type
  - Download formats: `.obj`, `.fbx`, `.blend`, `.gltf`
  
- **GrabCAD** https://grabcad.com/library
  - Industrial CAD library, often has `.step` or `.iges` files
  
- **Thingiverse** https://www.thingiverse.com
  - 3D print community, search: `"{Case Name}" case`

**License check:** Look for Creative Commons (CC-BY, CC0, etc.) - allows commercial reuse

---

### 2. **Official Manufacturer Photos** ⭐⭐⭐ (Deliverable #2)
- High-resolution, multi-angle, professional quality
- Essential for product visualization

**What to collect:**
- ✅ Front view (full case, straight-on)
- ✅ Back view (I/O ports clearly visible)
- ✅ Left & right side views
- ✅ Interior view (empty case, no components)
- ✅ Close-up: Rear I/O ports & connectors
- ✅ Optional: Top-down, special features, RGB areas

**Where to find:**
- Brand website product page: `/specifications` or `/gallery` section
- Amazon: Detailed product images (often 10+ angles available)
- Manufacturer press/media page: High-res assets
- Newegg, TechPowerUp: Product detail pages

---

### 4. **High-Quality Internet Photos** ⭐⭐ FALLBACK
- Reviews, YouTube unboxings, Reddit posts
- Tech reviewers often have amazing photography

**Where to search:**
- **YouTube Unboxing/Reviews:**
  - Search: `"{Case Name}" review` or `"{Case Name}" unboxing`
  - Pause video at good angles, screenshot
  - Channels: JayzTwoCents, Linus Tech Tips, GamersNexus, Hardware Unboxed
  
- **Reddit:**
  - r/pcmasterrace - search case name
  - r/buildapc - users post photos
  - r/pcgaming - enthusiast photos
  
- **Tech Review Sites:**
  - TechPowerUp (detailed case reviews with photos)
  - TechSpot (case comparisons)
  - Hardware Unboxed (in-depth reviews)

**⚠️ IMPORTANT - RGB Recoloring:**
If photos show **RGB lighting**, you must:
1. Capture the photo
2. Edit RGB colors to **FlipFlop brand colors:**
   - Primary: **Orange** `#FF6B35` (warm, energetic)
   - Secondary: **Blue** `#004E89` (cool, professional)
   - Gradient: Orange → Blue or alternating bands
3. Use photo editing (Photoshop, GIMP, Affinity) to recolor
4. Save as high-quality asset

**Example workflow:**
```
Original RGB: Purple, red, green, white
↓
Edit in GIMP/Photoshop: Select RGB areas → Replace color
↓
Target palette: Orange #FF6B35 + Blue #004E89
↓
Result: Case with FlipFlop brand colors
```

---

### 5. **Feature Description** ⭐ TEXT
- 2-3 sentences highlighting key selling points
- Used in customer builder & pre-built descriptions
- Help customers quickly understand what makes this case special

**What to include:**
- **Form factors:** "Supports ATX, M-ATX, Mini-ITX"
- **Key features:** "Tempered glass, RGB lighting, dual-chamber design"
- **Cooling:** "Supports dual radiators up to 360mm"
- **Aesthetics:** "Minimalist all-black aluminum frame"
- **Design philosophy:** "Purpose-built for silent operation"
- **Special advantages:** "Excellent cable management"
- **Price positioning:** "Budget-friendly alternative to premium brands"

**Template:**
```
"Lian Li Lancool 215 is a compact micro-ATX case with an 
aggressive mesh front panel design, supporting up to 3x 
120mm intake fans. Features tool-free drive installation 
and excellent airflow for budget gaming builds."
```

---

## Workflow

### Step 1: Visit /cases-3d-sourcing
- Shows top 30 cases by Amazon bestseller rank
- Geometry Green case at top
- Systematic checklist for each case

### Step 2: For each case, collect 4 deliverables:

**Deliverable 1: 3D Model** (pick best option)
- Check if manufacturer has CAD/3D files
- If not, search Sketchfab/GrabCAD for community models
- If not found, plan to hand-model from photos

**Deliverable 2: Photos** (multi-angle official)
- Collect manufacturer product photos from their website
- Amazon product images work as backup
- Need: Front, back, interior, rear ports/I/O

**Deliverable 3: YouTube Video** (official preferred)
- Search for official manufacturer product showcase
- If available, save link + screenshot key angles
- Edit any RGB areas to FlipFlop orange-blue gradient
- Fallback: High-quality review if no official video

**Deliverable 4: Description + KSP** (marketing copy)
- Form factors supported (ATX, M-ATX, Mini-ITX)
- Cooling capability (radiator support, fan slots)
- Key features (tempered glass, cable management, design style)
- Why it's special: value, performance, aesthetics, silence, etc

### Step 3: Mark complete
- Click "Complete" when all sources found
- Page tracks progress toward 30 cases

### Step 4: Begin 3D modeling
- Use CAD files as base (if available)
- Reference photos for detailing
- Ensure materials/colors match references
- Export as `.glb` for web (optimized)

### Step 5: Upload to database
- Update `has_3d_model = true` in database
- Associate model file with case

---

## Tips & Tricks

### CAD Search Hacks
```
site:thingiverse.com "Case Name"
site:grabcad.com "Case Name" filetype:step
"Case Name" CAD filetype:step
"Case Name" 3D model CAD STEP
```

### Photo Search Hacks
```
"Case Name" specifications site:manufacturer.com
"Case Name" gallery -reddit
"Case Name" review unboxing
"Case Name" inside photos teardown
```

### Quality Guidelines
- **CAD:** Use if manufacturer-provided
- **Photos:** Minimum 1920x1080 resolution
- **Description:** 2-3 sentences, highlight 2-3 key features
- **RGB:** Must be recolored to FlipFlop orange-blue

---

## Cases by Priority (Top 30)

Run query to get top 30 by bestseller_rank:
```sql
SELECT id, name, bestseller_rank, price, rating, review_count
FROM parts
WHERE category = 'case' AND bestseller_rank IS NOT NULL
ORDER BY bestseller_rank ASC
LIMIT 31;  -- 31 for Geometry Green
```

Plus your **Geometry Green** custom case at top.

---

## Storage Organization

Save all sourced assets:
```
/assets/cases/
├── {case-id}-cad/
│   └── model.step
├── {case-id}-photos/
│   ├── front.jpg
│   ├── back.jpg
│   ├── interior.jpg
│   └── ports-closeup.jpg
├── {case-id}-description.txt
└── index.json  (all case metadata + URLs)
```

---

## Estimated Timeline

- **Sourcing:** 1-2 hours per case (5-10 mins search + 10 mins photo collection)
- **Top 30 cases sourcing:** ~30-60 hours total
- **3D modeling:** Depends on your workflow (CAD → 1-2 hours, photos → 4-6 hours)

**Conservative estimate:** 60-90 hours for 30 complete cases

---

## When Stuck

- **No CAD anywhere?** → Use detailed photos + description, hand-model key features
- **RGB photos look bad?** → Recolor in post or find different angle
- **Missing specific angles?** → YouTube unboxing videos often have rotating views
- **Case discontinued?** → Use similar current-model photos + archive specs

---

## Next Steps

1. ✅ Open `/cases-3d-sourcing`
2. ✅ Start with Geometry Green (you already have this)
3. ✅ Move to #1 bestseller → work down the list
4. ✅ Save all sources (URLs, files) as you go
5. ✅ Mark complete when all 5 source types done
6. ✅ Begin 3D modeling once top 5 are sourced
7. ✅ Update database as models complete

---

**Goal:** 20-30 fully modeled cases in customer builder by end of month.

**Quality over quantity:** One perfect Corsair case beats three mediocre ones.
