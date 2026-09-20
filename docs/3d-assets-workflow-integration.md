# 3D Assets Workflow Integration

This document explains how the existing 3D Assets workflow integrates with the new unified bot approval system.

## Navigation Structure

The admin sidebar has two 3D-related entries:

1. **Bot Approvals** (`/approvals`) — Unified approval queue for all bot work (NEW)
2. **3D Assets** (`/cases-3d-priority`) — Existing two-step case workflow:
   - **Step 1:** `/cases-3d-priority` — "Photos & generation"
   - **Step 2:** `/components-3d-review` — "Model approval"

## Current 3D Assets Workflow (Existing)

### Step 1: Photos & Generation (`/cases-3d-priority`)

- Browse top-30 priority cases by rank
- Search manufacturer/third-party 3D models
- Curate 4 reference photos
- **Approve photo pack** (owner approval, not bot approval)
- Trigger Meshy generation

**Key behaviors:**
- Cases have `priority_3d_rank` (1-30 frozen snapshot)
- Sourcing evidence stored in `case.sourcing_3d_evidence` JSON
- Photo approval flow: select → approve → generate
- Generation creates `Component3DAsset` with status `MESHY_DRAFT`

### Step 2: Model Approval (`/components-3d-review`)

- Review batches of 10 generated models
- Approve/reject each model
- Batch must be fully decided before publishing
- Approved models become `VALIDATED` or `FINAL`

**Key behaviors:**
- Review batches are 10 models max
- Each model assigned to `review_batch_id`
- All 10 must have decisions before batch publishes
- Provenance, scale, poly count validation required

## New Unified Approval Queue (`/approvals`)

The new `/approvals` page handles:

1. **Photo packs** submitted by MeshyBot (NEW)
2. **3D models** submitted by MeshyBot (NEW)
3. **Playbooks** submitted by BuildBot (NEW)
4. **Pre-builts** submitted by BuildBot (NEW)
5. **Pricing** submitted by PricingBot (NEW)

## Integration Points

### MeshyBot Integration

MeshyBot can submit work to the approval queue **instead of** or **in parallel with** the existing manual workflow:

#### Option A: Manual + Bot Hybrid
- **Manual:** Michael uses `/cases-3d-priority` to approve photos and trigger generation
- **Bot:** MeshyBot monitors approved generations and auto-submits to `/bot-ingest/model-3d`
- **Review:** Michael reviews in `/approvals` (unified) or `/components-3d-review` (existing)

#### Option B: Bot-First Workflow
- **Bot:** MeshyBot submits photo packs to `/bot-ingest/photo-pack`
- **Approval:** Michael approves in `/approvals`
- **Bot:** MeshyBot triggers generation with approved photos
- **Bot:** MeshyBot submits model to `/bot-ingest/model-3d`
- **Approval:** Michael approves in `/approvals`

### Existing Assets Admin API

The existing `/api/assets-3d/*` endpoints remain unchanged:

- **GET** `/api/assets-3d/list` — List component 3D assets
- **POST** `/api/assets-3d/cases/{case_id}/generate` — Generate case model (manual trigger)
- **POST** `/api/assets-3d/review/batches` — Create review batch
- **POST** `/api/assets-3d/review/batches/{batch_id}/decision` — Approve/reject in batch
- **PATCH** `/api/assets-3d/assets/{asset_id}` — Update asset metadata

These APIs **coexist** with the new bot approval APIs.

## Migration Path

### Phase 1: Coexistence (Current)
- Both workflows available
- Manual workflow unchanged
- Bot workflow added alongside

### Phase 2: Bot-First (Future)
- MeshyBot submits all work through `/bot-ingest/*`
- Michael reviews in `/approvals` (unified queue)
- Existing `/cases-3d-priority` becomes read-only or deprecated

### Phase 3: Full Migration (Future)
- All bot work flows through unified approval
- Existing 3D Assets pages retired or repurposed
- `/approvals` becomes single source of truth

## Data Flow Comparison

### Existing Manual Workflow

```
Case → Manual photo selection → Owner approval → Meshy generation
  → Component3DAsset (MESHY_DRAFT) → Review batch → Batch approval
  → Component3DAsset (VALIDATED/FINAL) → Storefront
```

### New Bot Workflow

```
MeshyBot → POST /bot-ingest/photo-pack → BotApprovalQueue (pending)
  → Michael approves in /approvals → Status: approved
  → MeshyBot triggers generation → POST /bot-ingest/model-3d
  → BotApprovalQueue (pending) → Michael approves
  → Component3DAsset (VALIDATED) created → Storefront
```

## Component3DAsset Status Flow

### Manual Workflow
- `MISSING` → `MESHY_DRAFT` → `CLEANED` → `VALIDATED` → `FINAL`

### Bot Workflow
- Approved model creates `Component3DAsset` with status `VALIDATED` directly
- Skips intermediate `MESHY_DRAFT`/`CLEANED` if bot handles optimization

## Recommendations

1. **Start with coexistence:** Keep both workflows active during bot development
2. **Bot submits to approval queue:** All bot-generated work goes through `/bot-ingest/*`
3. **Manual workflow unchanged:** Existing `/cases-3d-priority` flow continues
4. **Unified review:** Michael can use `/approvals` for all bot work or continue using `/components-3d-review` for manual generations
5. **Gradual migration:** Once bots are stable, deprecate manual workflow

## Code References

### Existing 3D Assets
- **Admin pages:** `flipflop-admin/app/cases-3d-priority/page.tsx`, `flipflop-admin/app/components-3d-review/page.tsx`
- **API routes:** `flipflop-api/app/api/assets_admin.py`
- **Models:** `flipflop-api/app/models/component_3d_asset.py`, `flipflop-api/app/models/case.py`
- **Nav component:** `flipflop-admin/components/three-d-workflow-nav.tsx`

### New Bot Approvals
- **Admin page:** `flipflop-admin/app/approvals/page.tsx`
- **API routes:** `flipflop-api/app/api/bot_approvals.py`
- **Models:** `flipflop-api/app/models/bot_approval.py`
- **Migration:** `flipflop-api/alembic/versions/20260920_0001_bot_approval_queue.py`

## Testing Integration

1. **Manual workflow test:**
   ```
   Open http://localhost:3002/cases-3d-priority
   → Select case → Approve 4 photos → Generate
   → Open http://localhost:3002/components-3d-review
   → Review batch → Approve model
   ```

2. **Bot workflow test:**
   ```bash
   # Submit photo pack
   curl -X POST http://localhost:4311/api/bot-ingest/photo-pack \
     -H "Content-Type: application/json" \
     -d '{"sku":"TEST","category":"case","image_urls":["url1","url2","url3","url4"],"submitted_by":"MeshyBot"}'
   
   # Open http://localhost:3002/approvals
   # → Approve photo pack
   
   # Submit 3D model
   curl -X POST http://localhost:4311/api/bot-ingest/model-3d \
     -H "Content-Type: application/json" \
     -d '{"sku":"TEST","category":"case","glb_url":"https://...","submitted_by":"MeshyBot"}'
   
   # Open http://localhost:3002/approvals
   # → Approve model
   ```

3. **Verify both workflows work independently:**
   - Manual workflow creates `Component3DAsset` via existing routes
   - Bot workflow creates `BotApprovalQueue` entries
   - Both can coexist without conflicts
