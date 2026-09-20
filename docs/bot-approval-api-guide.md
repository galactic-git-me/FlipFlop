# Bot Approval API Guide

This guide documents the unified approval workflow for MeshyBot, BuildBot, and PricingBot.

## Architecture Overview

All bot-submitted work flows through a unified approval queue before becoming live:

1. **Bots** submit items via `/api/bot-ingest/*` endpoints
2. **Items** enter `bot_approval_queue` table with status `pending`
3. **Michael** reviews in admin tool at `/approvals`
4. **Approval** activates the resource (3D model, playbook, pricing)
5. **Rejection** retains the item for audit but prevents publication

No bot work reaches the storefront until explicitly approved in the admin tool.

## Database Schema

### bot_approval_queue

Unified queue for all pending approvals:

```sql
CREATE TABLE bot_approval_queue (
    id SERIAL PRIMARY KEY,
    approval_type VARCHAR(50) NOT NULL,  -- photo_pack | model_3d | playbook | prebuilt | pricing
    status VARCHAR(50) NOT NULL,          -- pending | approved | rejected | draft
    subject_sku VARCHAR(200),             -- For photo packs, 3D models
    subject_category VARCHAR(50),         -- case / component
    playbook_id VARCHAR(100),             -- For playbook/prebuilt/pricing proposals
    payload JSON NOT NULL,                -- Type-specific data (see below)
    sell_price_gbp FLOAT,
    total_cost_gbp FLOAT,
    est_margin_pct FLOAT,
    submitted_by VARCHAR(100),
    submitted_at TIMESTAMP NOT NULL,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,
    rejection_reason TEXT,
    notes TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP
);
```

### Payload Formats

#### photo_pack
```json
{
  "sku": "MONTECH-AIR100",
  "category": "case",
  "image_urls": [
    "https://example.com/photo1.jpg",
    "https://example.com/photo2.jpg",
    "https://example.com/photo3.jpg",
    "https://example.com/photo4.jpg"
  ],
  "argb_flags": {"has_argb": true, "zones": ["front", "side"]},
  "lighting_zones": {"front_fans": 3, "strip": 1}
}
```

#### model_3d
```json
{
  "sku": "MONTECH-AIR100",
  "category": "case",
  "glb_url": "https://flipflop.shop/media/case-montech-air100-v1.glb",
  "preview_image_url": "https://flipflop.shop/media/case-montech-air100-preview.jpg",
  "poly_count": 15420,
  "file_size_kb": 842,
  "source_image_refs": ["url1", "url2", "url3", "url4"]
}
```

#### playbook
```json
{
  "playbook_id": "FF-GVG-01",
  "customer_type": "Great-value Gaming",
  "budget_tier": "Budget",
  "core_components": [
    {
      "sku": "AMD-RYZEN-5-5600",
      "category": "cpu",
      "vendor": "AMD",
      "title": "AMD Ryzen 5 5600",
      "cost_gbp": 89.99,
      "lead_time_days": 2,
      "argb_flags": null
    }
    // ... more components
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
  "allowed_cases": ["MONTECH-AIR100", "MONTECH-SKY-TWO-GX"]
}
```

#### prebuilt
```json
{
  "build_id": "prometheus-v2",
  "build_name": "Prometheus Gaming Rig",
  "components": [
    {"sku": "...", "category": "cpu", "cost_gbp": 299.99},
    {"sku": "...", "category": "gpu", "cost_gbp": 449.99}
  ],
  "total_cost_gbp": 1249.50
}
```

#### pricing
```json
{
  "target_type": "playbook",
  "target_id": "FF-GVG-01",
  "pricing_rationale": "Competitive with similar builds on Scan/Overclockers; £100 delivery buffer included",
  "market_comparison": {
    "scan_uk": 1599.99,
    "overclockers": 1649.99,
    "currys": 1699.99
  },
  "delivery_buffer_gbp": 100.00,
  "upsell_delta_sell_gbp": 120.00,
  "upsell_delta_cost_gbp": 80.00
}
```

## Bot API Endpoints

Base URL: `http://localhost:4311/api/bot-ingest` (dev) or configured API URL

### Submit Photo Pack (MeshyBot)

**POST** `/api/bot-ingest/photo-pack`

```json
{
  "sku": "MONTECH-AIR100",
  "category": "case",
  "image_urls": ["url1", "url2", "url3", "url4"],
  "argb_flags": {"has_argb": true},
  "lighting_zones": {"front_fans": 3},
  "submitted_by": "MeshyBot"
}
```

**Response:**
```json
{
  "status": "success",
  "id": 42,
  "message": "Photo pack submitted for approval"
}
```

### Submit 3D Model (MeshyBot)

**POST** `/api/bot-ingest/model-3d`

```json
{
  "sku": "MONTECH-AIR100",
  "category": "case",
  "glb_url": "https://flipflop.shop/media/case-montech-air100-v1.glb",
  "preview_image_url": "https://flipflop.shop/media/preview.jpg",
  "poly_count": 15420,
  "file_size_kb": 842,
  "source_image_refs": ["url1", "url2", "url3", "url4"],
  "submitted_by": "MeshyBot"
}
```

**Response:**
```json
{
  "status": "success",
  "id": 43,
  "message": "3D model submitted for approval"
}
```

### Submit Playbook (BuildBot)

**POST** `/api/bot-ingest/playbook`

```json
{
  "playbook_id": "FF-GVG-01",
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
}
```

**Response:**
```json
{
  "status": "success",
  "id": 44,
  "message": "Playbook submitted for approval"
}
```

### Submit Pre-built (BuildBot)

**POST** `/api/bot-ingest/prebuilt`

```json
{
  "build_id": "prometheus-v2",
  "build_name": "Prometheus Gaming Rig",
  "components": [
    {"sku": "AMD-RYZEN-7-9800X3D", "category": "cpu", "cost_gbp": 449.99},
    {"sku": "RTX-5080-16GB", "category": "gpu", "cost_gbp": 799.99}
  ],
  "total_cost_gbp": 1449.50,
  "sell_price_gbp": 1849.99,
  "est_margin_pct": 21.6,
  "submitted_by": "BuildBot"
}
```

**Response:**
```json
{
  "status": "success",
  "id": 45,
  "message": "Pre-built submitted for approval"
}
```

### Submit Pricing Proposal (PricingBot)

**POST** `/api/bot-ingest/pricing`

```json
{
  "target_type": "playbook",
  "target_id": "FF-GVG-01",
  "sell_price_gbp": 799.99,
  "total_cost_gbp": 599.50,
  "est_margin_pct": 25.1,
  "delivery_buffer_gbp": 75.00,
  "upsell_delta_sell_gbp": 120.00,
  "upsell_delta_cost_gbp": 80.00,
  "pricing_rationale": "Competitive with Scan UK; includes £75 delivery buffer",
  "market_comparison": {
    "scan_uk": 849.99,
    "overclockers": 899.99
  },
  "submitted_by": "PricingBot"
}
```

**Response:**
```json
{
  "status": "success",
  "id": 46,
  "message": "Pricing proposal submitted for approval"
}
```

## Admin Endpoints

Admin endpoints require authentication (loopback auto-auth in dev, JWT in production).

### Get Approval Summary

**GET** `/api/bot-approvals/summary`

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

### Get Pending Approvals

**GET** `/api/bot-approvals/pending?approval_type=model_3d&limit=50&offset=0`

Query params:
- `approval_type` (optional): Filter by type
- `limit` (optional, default 50, max 200)
- `offset` (optional, default 0)

**Response:** Array of approval items (see ApprovalItemOut schema)

### Get Approval History

**GET** `/api/bot-approvals/history?status=approved&limit=50`

Query params:
- `status` (optional): `approved` or `rejected`
- `approval_type` (optional)
- `limit` (optional, default 50, max 200)
- `offset` (optional, default 0)

**Response:** Array of historical approval items

### Make Approval Decision

**POST** `/api/bot-approvals/{item_id}/decision`

```json
{
  "action": "approve",
  "rejection_reason": null,
  "notes": "Looks good, poly count is acceptable"
}
```

or

```json
{
  "action": "reject",
  "rejection_reason": "Poly count too high (>20k), needs optimization",
  "notes": null
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

## Admin UI

Navigate to `http://localhost:3002/approvals` in flipflop-admin.

Features:
- **Summary dashboard** showing pending counts by type
- **Filter by type** (click a summary card)
- **Approve/Reject** buttons on each item
- **Visual previews** for photo packs and 3D models
- **Component lists** for playbooks/prebuilts
- **Pricing breakdown** showing sell/cost/margin

## Integration Flow Examples

### MeshyBot: Photo Pack → 3D Model

1. **Submit photo pack:**
   ```bash
   curl -X POST http://localhost:4311/api/bot-ingest/photo-pack \
     -H "Content-Type: application/json" \
     -d '{
       "sku": "MONTECH-AIR100",
       "category": "case",
       "image_urls": ["url1", "url2", "url3", "url4"],
       "submitted_by": "MeshyBot"
     }'
   ```

2. **Michael approves** in admin UI → photo pack status becomes `approved`

3. **MeshyBot triggers Meshy generation** using approved photos

4. **Submit 3D model:**
   ```bash
   curl -X POST http://localhost:4311/api/bot-ingest/model-3d \
     -H "Content-Type: application/json" \
     -d '{
       "sku": "MONTECH-AIR100",
       "category": "case",
       "glb_url": "https://...",
       "preview_image_url": "https://...",
       "poly_count": 15420,
       "file_size_kb": 842,
       "submitted_by": "MeshyBot"
     }'
   ```

5. **Michael approves** → model becomes active in `component_3d_assets` table

### BuildBot: Playbook → PricingBot → Approval

1. **BuildBot submits playbook** with components, upsells, allowed cases
2. **PricingBot submits pricing proposal** for same playbook_id
3. **Michael reviews both** in admin UI:
   - Playbook shows component list, no pricing yet
   - Pricing proposal shows sell/cost/margin breakdown
4. **Michael approves both** → playbook becomes `live`, pricing applied

### BuildBot: Pre-built (e.g. Prometheus)

1. **BuildBot submits pre-built BOM:**
   ```bash
   curl -X POST http://localhost:4311/api/bot-ingest/prebuilt \
     -H "Content-Type: application/json" \
     -d '{
       "build_id": "prometheus-v2",
       "build_name": "Prometheus Gaming Rig",
       "components": [...],
       "total_cost_gbp": 1449.50,
       "submitted_by": "BuildBot"
     }'
   ```

2. **PricingBot submits pricing** (optional, or BuildBot includes it)

3. **Michael approves** → Prometheus £1,449 provisional becomes approved

## Status Flow

```
draft → pending → approved ✓ (live on storefront)
                ↘ rejected ✗ (retained for audit, not live)
```

- **draft**: Created but not submitted (reserved for future workflow)
- **pending**: Awaiting Michael's approval
- **approved**: Live and visible to customers
- **rejected**: Not live, retained for review/iteration

## Testing Locally

1. **Start services:**
   ```bash
   pm2 start all
   ```

2. **Apply migration:**
   ```bash
   cd flipflop-api
   alembic upgrade head
   ```

3. **Submit test item:**
   ```bash
   curl -X POST http://localhost:4311/api/bot-ingest/photo-pack \
     -H "Content-Type: application/json" \
     -d '{
       "sku": "TEST-CASE-001",
       "category": "case",
       "image_urls": [
         "https://via.placeholder.com/800x600/1",
         "https://via.placeholder.com/800x600/2",
         "https://via.placeholder.com/800x600/3",
         "https://via.placeholder.com/800x600/4"
       ],
       "submitted_by": "TestBot"
     }'
   ```

4. **Open admin:** `http://localhost:3002/approvals`

5. **Approve/Reject** the test item

## Authentication Notes

- **Dev (loopback):** Admin endpoints allow localhost without JWT
- **Production:** Admin endpoints require `Authorization: Bearer <token>`
- **Bot endpoints:** Currently unauthenticated; extend with API keys/tokens as needed

## Future Extensions

- **Batch approval** (approve multiple items at once)
- **Approval delegation** (assign items to specific reviewers)
- **Approval history/audit log** per item
- **Bot API authentication** (API keys, service accounts)
- **Webhook notifications** when items are approved/rejected
- **3D model viewer** embedded in approval UI (three.js/react-three-fiber)
