# Manual Build Screen — Design Spec
**Date:** 2026-06-09  
**Route:** `/flips` (replaces current Inventory screen)  
**Sidebar label:** "Manual Build" (was "Inventory")

---

## Overview

A screen for composing a PC build from individual components, tracking what was paid for each, and requesting an LLM-powered marketplace valuation with high/mid/low resale estimates and enhancement suggestions. Builds are saved by name and auto-saved on every change.

---

## Page Structure

Three vertical regions:

### 1. Build Header Bar
- **Build name** — inline-editable text field; shown prominently at top
- **New Build** button — creates a fresh unnamed build
- **Load build** dropdown — lists all saved builds by name + last-updated date; selecting one loads it
- **Auto-save indicator** — subtle "Saved ✓" flash after each debounced save; no explicit Save button after first creation

First-time (new build): a "Name this build" prompt appears before anything is added (can be dismissed to use a default name like "Build #3").

### 2. Component List (vertical rows)

Fixed slots in order, each with a colour accent:

| Slot | Accent colour |
|------|--------------|
| Base PC | purple |
| CPU | blue |
| GPU | cyan |
| RAM | amber |
| Storage | green |
| PSU | red |
| Case | indigo |
| Motherboard | teal |
| Cooling | sky |

**Empty slot row** — dimmed, dashed border. Shows slot label + "Click to add…". Clicking anywhere opens the entry modal.

**Filled slot row** — solid border with colour accent. Shows:
- Slot label (coloured)
- Component name
- Price paid (inline-editable number field, £)
- Source badge: catalogue link (with thumbnail) or "manual"
- Remove × button

**"+ Add custom slot"** row at the bottom — opens a simplified modal where the user types a slot name, then proceeds to the normal entry modal.

### 3. Pinned Footer Bar

**Before evaluation:**
```
Total paid: £XXX        [ 🤖 Evaluate Build → ]
```

**After evaluation (expands upward):**
```
┌─────────────────────────────────────────────────────┐
│  AI ASSESSMENT                          [Re-evaluate]│
│                                                      │
│  LOW £320   MID £390   HIGH £450                     │
│  Profit:  £+70   £+140   £+200                       │
│                                                      │
│  "This build centres on the RTX 3060 which..."      │
│                                                      │
│  Suggestions:                                        │
│  • Swap stock cooler → +£15 resale                  │
│  • Add 2nd NVMe SSD → +£20 resale                   │
│  • Clean/repaste CPU → +£10 resale                  │
└─────────────────────────────────────────────────────┘
Total paid: £250        [ 🤖 Re-evaluate ]
```

---

## Component Entry Modal

Opens when clicking any empty slot row. Two tabs:

### Catalogue Tab
- Debounced search box querying the `parts` table
- Results list: thumbnail · title · price · source name
- Clicking a result shows a "Price paid: £___" field + Confirm button
- If no results: "No catalogue matches — switch to Manual tab"

### Manual Tab
- **Name** — free text
- **Price paid** — number field (£)
- Confirm button

---

## Auto-Save Behaviour

Every state change (component added/removed/edited, name changed) triggers a debounced `PATCH /manual-builds/{id}` call (300ms debounce). A small "Saved ✓" indicator appears briefly after each successful save. No data is lost on page refresh or navigation.

---

## Backend

### Database — new table: `manual_builds`

```sql
CREATE TABLE manual_builds (
  id            SERIAL PRIMARY KEY,
  name          TEXT NOT NULL DEFAULT 'Untitled Build',
  components    JSONB NOT NULL DEFAULT '[]',
  total_cost    NUMERIC(10,2),
  last_evaluation JSONB,           -- stores low/mid/high + suggestions
  created_at    TIMESTAMP DEFAULT now(),
  updated_at    TIMESTAMP DEFAULT now()
);
```

`components` JSON shape (array of objects):
```json
[
  {
    "slot":        "GPU",
    "name":        "RTX 3060 12GB",
    "price_paid":  170.00,
    "source":      "catalogue",
    "part_id":     42,
    "listing_url": "https://...",
    "image_url":   "https://..."
  }
]
```

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/manual-builds` | Create new build (returns id) |
| `GET` | `/manual-builds` | List all builds (id, name, total_cost, updated_at) |
| `GET` | `/manual-builds/{id}` | Load full build |
| `PATCH` | `/manual-builds/{id}` | Auto-save (name + components) |
| `DELETE` | `/manual-builds/{id}` | Delete a build |
| `POST` | `/manual-builds/{id}/evaluate` | Run LLM evaluation; saves result to build row |

### Evaluation endpoint

Sends component list to Claude with a prompt that:
- Summarises the full build spec
- Asks for low/mid/high resale price estimates for the UK secondhand market
- Asks for up to 3 actionable enhancement suggestions with estimated uplift

Returns:
```json
{
  "low":  320,
  "mid":  390,
  "high": 450,
  "narrative": "This build...",
  "suggestions": [
    { "text": "Swap stock cooler for budget aftermarket", "uplift": 15 },
    { "text": "Add a second NVMe SSD", "uplift": 20 },
    { "text": "Clean and repaste CPU", "uplift": 10 }
  ]
}
```

---

## Frontend Files

| File | Change |
|------|--------|
| `app/flips/page.tsx` | Full replacement with Manual Build screen |
| `components/manual-build/BuildRow.tsx` | Single component slot row |
| `components/manual-build/EntryModal.tsx` | Two-tab add/edit modal |
| `components/manual-build/EvalPanel.tsx` | Expandable evaluation results panel |
| `lib/api.ts` | Add `ManualBuild` types + API calls |
| `components/sidebar.tsx` | Rename nav label "Inventory" → "Manual Build" |

---

## Out of Scope

- Sharing or exporting builds
- Build comparison (multiple builds side by side)
- Marketplace listing generation from a build
- Mobile layout optimisation
