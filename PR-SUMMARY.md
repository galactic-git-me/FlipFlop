# Pull Request Summary: Unified Bot Approval Workflow

**Branch:** `cursor/unified-bot-approvals-2b4a`  
**Base:** `dev`  
**Status:** Ready for review

---

## Overview

Extends FlipFlop admin and API to support **unified pending-approval workflows** for MeshyBot, BuildBot, and PricingBot. Michael can now approve all bot-team work in the admin tool only (no chat approvals).

---

## What's New

### 1. Database Schema

Three new tables for approval tracking:

- **`bot_approval_queue`** — Unified approval queue for all bot submissions
  - Stores pending items from all bots (photo packs, 3D models, playbooks, prebuilts, pricing)
  - Status: `pending` → `approved` | `rejected`
  - Tracks submission time, reviewer, rejection reasons

- **`playbook_proposals_extended`** — Extended playbook proposal tracking
  - Core components BOM, upsells, allowed cases
  - Customer type, budget tier (Value/Balanced/Performance)
  - Pricing fields (may be empty until PricingBot fills them)

- **`pricing_proposals`** — Pricing proposal tracking
  - Target type (playbook/prebuilt) and target ID
  - Sell price, cost, margin, delivery buffer
  - Market comparison data, pricing rationale

### 2. API Endpoints

#### Bot Ingest Endpoints (for bots to submit work)

- **POST** `/api/bot-ingest/photo-pack` — MeshyBot submits 4 reference photos
  - SKU, category, image URLs, ARGB flags, lighting zones
  
- **POST** `/api/bot-ingest/model-3d` — MeshyBot submits generated .glb
  - GLB URL, preview image, poly count, file size, source images
  
- **POST** `/api/bot-ingest/playbook` — BuildBot submits curated playbook
  - Playbook ID, customer type, budget tier, core components, upsells, allowed cases
  
- **POST** `/api/bot-ingest/prebuilt` — BuildBot submits pre-built BOM
  - Build ID, name, components, total cost
  
- **POST** `/api/bot-ingest/pricing` — PricingBot submits pricing proposal
  - Target (playbook/prebuilt), sell price, cost, margin, delivery buffer, market comparison

#### Admin Endpoints (for Michael to approve/reject)

- **GET** `/api/bot-approvals/summary` — Pending counts by type
- **GET** `/api/bot-approvals/pending` — List pending items (filterable by type)
- **GET** `/api/bot-approvals/history` — List approved/rejected items
- **POST** `/api/bot-approvals/{id}/decision` — Approve or reject with optional notes

### 3. Admin UI

New **Bot Approvals** page at `/approvals`:

- **Summary dashboard** showing pending counts by type (photo packs, 3D models, playbooks, prebuilts, pricing)
- **Filter by type** — Click a summary card to filter
- **Visual previews** for photo packs (4-image grid) and 3D models (GLB link + preview image)
- **Component lists** for playbooks/prebuilts (scrollable table)
- **Pricing breakdown** — Sell price, cost, margin prominently displayed
- **One-click approve/reject** — Approve button (green), Reject button (red with reason prompt)

Added to sidebar navigation between "Email Events" and "3D Assets".

### 4. Integration with Existing 3D Assets Workflow

The existing 3D Assets workflow **continues to work unchanged**:

- **Manual workflow:** `/cases-3d-priority` (Photos & generation) → `/components-3d-review` (Model approval)
- **Bot workflow:** MeshyBot → `/bot-ingest/*` → `/approvals` (unified queue)

Both workflows coexist. Future migration will consolidate into bot-first workflow.

---

## Approval Flow

```
Bot submits work
  ↓
BotApprovalQueue (status: pending)
  ↓
Michael reviews in /approvals
  ↓
Approve: Resource becomes live (Component3DAsset, Playbook, etc.)
  OR
Reject: Retained for audit, not live
```

**Status Machine:**
- `draft` → `pending` → `approved` ✓ (live on storefront)
                    ↘ `rejected` ✗ (retained for audit, not live)

---

## Supported Bot Work Types

### 1. Photo Packs (MeshyBot)
4 reference photos for 3D generation. Each pack includes:
- SKU, category (case/component)
- 4 image URLs (exactly 4 required)
- ARGB flags (optional)
- Lighting zones (optional)

### 2. 3D Models (MeshyBot)
Generated .glb models ready for review. Each submission includes:
- SKU, category
- GLB URL (published model file)
- Preview image URL
- Poly count, file size (KB)
- Source image references

### 3. Playbooks (BuildBot)
Curated build configurations (24 playbooks total). Each includes:
- Playbook ID (e.g. `FF-GVG-01`)
- Customer type (e.g. "Great-value Gaming")
- Budget tier (Value/Balanced/Performance)
- Core components BOM (SKU, category, vendor, cost, lead time)
- Upsells (category, from/to SKU, delta cost/sell)
- Allowed cases (array of SKUs)
- Pricing (optional, may be filled by PricingBot)

### 4. Pre-builts (BuildBot)
Fixed BOM builds (e.g. Prometheus). Each includes:
- Build ID, name
- Components (SKU, category, cost)
- Total cost
- Sell price (optional)
- Margin (optional)

### 5. Pricing (PricingBot)
Price proposals for playbooks/prebuilts. Each includes:
- Target type (`playbook` or `prebuilt`)
- Target ID (playbook ID or build ID)
- Sell price (GBP)
- Total cost (GBP)
- Estimated margin (%)
- Delivery buffer (£50-£100, optional)
- Upsell delta sell/cost (optional)
- Pricing rationale (text)
- Market comparison (competitor prices)

---

## Files Changed

### Backend (flipflop-api)

**New files:**
- `app/models/bot_approval.py` — Models for approval queue, playbook proposals, pricing proposals
- `app/api/bot_approvals.py` — Admin and bot API endpoints
- `alembic/versions/20260920_0001_bot_approval_queue.py` — Database migration

**Modified:**
- `app/main.py` — Registered new routers
- `app/models/__init__.py` — Exported new models

### Frontend (flipflop-admin)

**New files:**
- `app/approvals/page.tsx` — Approval queue UI

**Modified:**
- `components/sidebar.tsx` — Added "Bot Approvals" nav entry

### Documentation

**New files:**
- `docs/bot-approval-api-guide.md` — Comprehensive API documentation
- `docs/3d-assets-workflow-integration.md` — Integration guide for existing workflow

---

## Testing Locally

### 1. Start Services

```bash
pm2 start all
```

Verify:
- `gemradar-api-18000` running (FastAPI backend)
- `flipflop-admin-3002` running (Next.js admin)

### 2. Apply Migration

```bash
cd flipflop-api
alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Running upgrade ... -> 20260920_0001, bot_approval_queue
```

### 3. Submit Test Photo Pack

```bash
curl -X POST http://localhost:4311/api/bot-ingest/photo-pack \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "TEST-CASE-001",
    "category": "case",
    "image_urls": [
      "https://via.placeholder.com/800x600/FF6B6B/FFFFFF?text=Photo+1",
      "https://via.placeholder.com/800x600/4ECDC4/FFFFFF?text=Photo+2",
      "https://via.placeholder.com/800x600/45B7D1/FFFFFF?text=Photo+3",
      "https://via.placeholder.com/800x600/FFA07A/FFFFFF?text=Photo+4"
    ],
    "submitted_by": "TestBot"
  }'
```

Expected response:
```json
{
  "status": "success",
  "id": 1,
  "message": "Photo pack submitted for approval"
}
```

### 4. Submit Test 3D Model

```bash
curl -X POST http://localhost:4311/api/bot-ingest/model-3d \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "TEST-CASE-001",
    "category": "case",
    "glb_url": "https://example.com/test-model.glb",
    "preview_image_url": "https://via.placeholder.com/400x400/9B59B6/FFFFFF?text=3D+Model",
    "poly_count": 15420,
    "file_size_kb": 842,
    "submitted_by": "MeshyBot"
  }'
```

### 5. Submit Test Playbook

```bash
curl -X POST http://localhost:4311/api/bot-ingest/playbook \
  -H "Content-Type: application/json" \
  -d '{
    "playbook_id": "FF-TEST-01",
    "customer_type": "Great-value Gaming",
    "budget_tier": "Budget",
    "core_components": [
      {
        "sku": "AMD-RYZEN-5-5600",
        "category": "cpu",
        "vendor": "AMD",
        "title": "AMD Ryzen 5 5600",
        "cost_gbp": 89.99,
        "lead_time_days": 2
      },
      {
        "sku": "RTX-5050-8GB",
        "category": "gpu",
        "vendor": "NVIDIA",
        "title": "NVIDIA GeForce RTX 5050 8GB",
        "cost_gbp": 249.99,
        "lead_time_days": 3
      }
    ],
    "upsells": [
      {
        "category": "gpu",
        "from_sku": "RTX-5050-8GB",
        "to_sku": "RTX-5060-12GB",
        "delta_cost_gbp": 80.00,
        "delta_sell_gbp": 120.00,
        "reason": "Better 1440p performance"
      }
    ],
    "allowed_cases": ["MONTECH-AIR100"],
    "sell_price_gbp": 799.99,
    "total_cost_gbp": 599.50,
    "est_margin_pct": 25.1,
    "submitted_by": "BuildBot"
  }'
```

### 6. View in Admin

Open: `http://localhost:3002/approvals`

Expected:
- Summary dashboard shows 3 pending items (1 photo pack, 1 3D model, 1 playbook)
- Click on each card to see details
- Photo pack shows 4-image grid
- 3D model shows GLB link and preview
- Playbook shows component list with pricing

### 7. Approve Items

Click **Approve** button on each item.

Expected:
- Status changes to `approved`
- Item disappears from pending queue
- Summary counts update
- Item appears in history (if you navigate to history view)

### 8. Reject an Item

1. Submit another test item
2. Click **Reject** button
3. Enter rejection reason: "Poly count too high"
4. Confirm

Expected:
- Status changes to `rejected`
- Rejection reason saved
- Item moves to history

---

## API Contracts

### Admin Endpoints

**Base URL:** `http://localhost:4311/api/bot-approvals`

#### GET /summary

**Response:**
```json
{
  "total_pending": 12,
  "pending_photo_packs": 3,
  "pending_models_3d": 2,
  "pending_playbooks": 4,
  "pending_prebuilts": 1,
  "pending_pricing": 2
}
```

#### GET /pending

**Query params:**
- `approval_type` (optional): `photo_pack` | `model_3d` | `playbook` | `prebuilt` | `pricing`
- `limit` (optional, default 50, max 200)
- `offset` (optional, default 0)

**Response:** Array of approval items

#### POST /{item_id}/decision

**Request:**
```json
{
  "action": "approve",
  "rejection_reason": null,
  "notes": "Looks good"
}
```

**Response:**
```json
{
  "status": "success",
  "item_id": 42,
  "action": "approve",
  "new_status": "approved"
}
```

### Bot Endpoints

**Base URL:** `http://localhost:4311/api/bot-ingest`

All endpoints return:
```json
{
  "status": "success",
  "id": 123,
  "message": "... submitted for approval"
}
```

See `docs/bot-approval-api-guide.md` for full schemas.

---

## Migration Strategy

This PR implements **Phase 1: Coexistence**.

### Phase 1: Coexistence (Current)
- Both manual and bot workflows active
- Existing 3D Assets workflow unchanged
- New bot approval workflow added alongside
- Michael can use either or both

### Phase 2: Bot-First (Future)
- MeshyBot submits all work through `/bot-ingest/*`
- Michael reviews in `/approvals` (unified queue)
- Existing `/cases-3d-priority` becomes read-only

### Phase 3: Full Migration (Future)
- All bot work flows through unified approval
- Existing 3D Assets pages retired or repurposed
- `/approvals` becomes single source of truth

---

## Related Context

### Existing Foundation
- **3D Assets workflow:** `flipflop-admin/app/cases-3d-priority/`, `flipflop-admin/app/components-3d-review/`
- **Assets API:** `flipflop-api/app/api/assets_admin.py`
- **Component3DAsset model:** `flipflop-api/app/models/component_3d_asset.py`
- **Curated builds data:** `flipflop-api/data/curated_build_definitions.json`

### Future Work
- BuildBot integration (uses playbook submission endpoints)
- PricingBot integration (uses pricing proposal endpoints)
- Batch approval (approve multiple items at once)
- Bot authentication (API keys, service accounts)
- Webhook notifications

---

## Done Checklist

- [x] Michael can approve photo packs, 3D models, playbook/pre-built proposals, and price proposals entirely in flipflop-admin
- [x] APIs exist for bots to submit pending items
- [x] Existing 3D Assets flow is reused/extended, not abandoned
- [x] Clear API contracts documented
- [x] Database migration created
- [x] Admin UI paths documented
- [x] Local testing guide provided
- [x] Branch pushed with clear commit messages

---

## How to Create PR

Since automated PR creation is restricted, please create manually:

1. Go to: https://github.com/galactic-git-me/FlipFlop/pull/new/cursor/unified-bot-approvals-2b4a
2. Base: `dev`
3. Compare: `cursor/unified-bot-approvals-2b4a`
4. Title: **Unified bot approval workflow in FlipFlop admin**
5. Body: Copy from this document or use condensed version
6. Mark as **Draft** (recommended for review before merging)

---

## Contact

For questions or clarification, reference:
- `docs/bot-approval-api-guide.md` — Full API documentation
- `docs/3d-assets-workflow-integration.md` — Integration with existing workflow
- This PR summary document
