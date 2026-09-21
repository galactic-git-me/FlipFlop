## Curated Component Availability System

**Status**: 🏗️ Ready for implementation  
**Branch**: `cursor/curated-playbooks-storefront-13ea`

## Overview

Implements **primary + backup SKU availability** for curated playbooks, enabling automatic failover when components are out of stock.

### Problem Statement

- **Daily FlipFlopXtension scrapes too slow alone** for real-time availability
- Shop needs **live vendor listing availability** checks for primary SKUs
- Must **soft-swap to backup** when primary is OOS
- Never sell a **hard-OOS configuration**
- Analytics must tag orders with `sku_source=primary|backup`

### Design Goals

1. **Primary + Backup SKUs**: Each component slot supports multiple SKUs (compat-locked by BuildBot)
2. **Live Availability Checks**: Check vendor availability before showing "Add to Cart"
3. **Automatic Failover**: Soft-swap to backup when primary OOS
4. **Shop Visibility**: Hide tier/ship when all SKUs OOS
5. **Analytics Tagging**: Track which SKU source was used (primary vs backup)
6. **Approval Flow**: Permanent BOM replacements require Michael Approve
7. **MeshyBot Integration**: Remesh only if visible part swaps (case, GPU, etc.)

---

## Architecture

### Data Model

#### 1. `curated_component_skus` Table

Stores primary + backup SKUs for each component slot.

**Key Fields**:
- `curated_build_id` - Build ID (e.g., "FF-GVG-02")
- `component_slot` - Slot type (cpu, gpu, ram, etc.)
- `is_primary` - True for primary, False for backup
- `priority` - 0=primary, 1=first backup, 2=second backup, etc.
- `component_title` - Human-readable component name
- `preferred_vendor` - Vendor to check (overclockers, scan, amazon, etc.)
- `vendor_sku` - Vendor's product SKU/code
- `vendor_url` - Direct product page URL
- `availability_status` - Current status (in_stock/low_stock/out_of_stock/unknown/discontinued)
- `estimated_stock_level` - Quantity available (if known)
- `requires_approval_for_swap` - True for visible parts (case, GPU)
- `requires_remesh` - True if MeshyBot remesh needed
- `is_active` - False when SKU deactivated/replaced

**Example**:
```json
{
  "id": 1,
  "curated_build_id": "FF-GVG-02",
  "component_slot": "gpu",
  "is_primary": true,
  "priority": 0,
  "component_title": "AMD Radeon RX 9060 XT 16GB",
  "preferred_vendor": "overclockers",
  "vendor_sku": "GX-123-RX",
  "vendor_url": "https://overclockers.co.uk/...",
  "availability_status": "in_stock",
  "estimated_stock_level": 12,
  "requires_approval_for_swap": true,
  "requires_remesh": true,
  "is_active": true
}
```

#### 2. `curated_build_availability` Table

Tracks overall availability for each build.

**Key Fields**:
- `curated_build_id` - Build ID
- `is_available` - Can we sell it? (Boolean)
- `availability_status` - Overall status (available/low_stock/out_of_stock)
- `components_status` - Per-slot status summary (JSON)
- `active_skus` - Currently active SKUs (JSON map)
- `using_backup_count` - How many backups currently in use
- `backup_slots` - List of slots using backup SKUs
- `is_visible_on_shop` - Should show on storefront?
- `hidden_reason` - Why hidden (if applicable)
- `sku_swap_count` - Total lifetime swaps

**Example**:
```json
{
  "curated_build_id": "FF-GVG-02",
  "is_available": true,
  "using_backup_count": 1,
  "backup_slots": ["gpu"],
  "active_skus": {
    "cpu": {
      "id": 10,
      "title": "AMD Ryzen 5 9600X",
      "is_primary": true,
      "sku_source": "primary"
    },
    "gpu": {
      "id": 12,
      "title": "NVIDIA GeForce RTX 5060 16GB",
      "is_primary": false,
      "sku_source": "backup"
    }
  },
  "is_visible_on_shop": true,
  "sku_swap_count": 3
}
```

#### 3. `sku_swap_events` Table

Audit trail for all SKU swaps.

**Key Fields**:
- `curated_build_id` - Build ID
- `component_slot` - Slot that was swapped
- `from_sku_id` - Previous SKU (null if initial)
- `to_sku_id` - New SKU
- `swap_reason` - Why swapped (out_of_stock/price_change/manual/etc.)
- `swap_source` - Who/what triggered (system/admin/bot)
- `triggered_by_order_id` - Order that triggered swap (if applicable)
- `approved_by` - Admin who approved manual swap
- `swapped_at` - When swap occurred

---

## Services

### `CuratedAvailabilityService`

**Core Methods**:

1. **`check_sku_availability(sku, force_refresh)`**
   - Checks vendor availability for a single SKU
   - Uses vendor-specific checker or falls back to extension data
   - Caches result for 15 minutes (configurable)
   - Updates SKU record with status + stock level

2. **`get_available_sku_for_slot(build_id, slot, check_live)`**
   - Returns best available SKU for a component slot
   - Priority: Primary (if in stock) → First backup → Second backup → ...
   - Returns None if all SKUs OOS

3. **`update_build_availability(build_id, check_live)`**
   - Updates overall availability for a build
   - Checks all component slots
   - Determines which SKUs are active
   - Computes backup usage count
   - Sets shop visibility

4. **`swap_sku(build_id, slot, from_sku_id, to_sku_id, reason, ...)`**
   - Records a SKU swap event
   - Updates swap counters
   - Logs to analytics

5. **`get_build_bom_with_availability(build_id, check_live)`**
   - Returns complete BOM with availability-aware SKU selection
   - Includes sku_source=primary|backup for each component
   - Shop uses this to display current configuration

### `VendorAvailabilityChecker` (Abstract Interface)

**Purpose**: Allows pluggable vendor integrations

**Methods**:
- `check_availability(vendor_sku, vendor_url)` → (status, stock_level)

**Implementations**:
- `ExtensionDataChecker` - Uses FlipFlopXtension scrape data (fallback)
- `OverclockersChecker` - (TODO) Overclockers API integration
- `ScanChecker` - (TODO) Scan.co.uk API integration
- `AmazonChecker` - (TODO) Amazon SP API integration

**Adding New Vendor**:
```python
class OverclockersChecker(VendorAvailabilityChecker):
    async def check_availability(self, vendor_sku, vendor_url):
        # Call Overclockers API
        response = await overclockers_api.check_stock(vendor_sku)
        
        if response.in_stock:
            return SKUAvailabilityStatus.IN_STOCK, response.quantity
        else:
            return SKUAvailabilityStatus.OUT_OF_STOCK, 0

# Register in CuratedAvailabilityService.__init__:
self.vendor_checkers["overclockers"] = OverclockersChecker()
```

---

## API Endpoints

### Public Endpoints (No Auth)

#### `GET /api/public/curated-availability/build/{build_id}`

Get availability status and BOM for a build.

**Query Params**:
- `check_live` (bool, default=false) - Check live vendor availability

**Response**:
```json
{
  "build_id": "FF-GVG-02",
  "is_available": true,
  "using_backup_count": 1,
  "components": {
    "cpu": {
      "slot": "cpu",
      "title": "AMD Ryzen 5 9600X",
      "sku_source": "primary",
      "is_backup": false,
      "availability_status": "in_stock",
      "vendor": "overclockers",
      "checked_at": "2026-09-21T11:30:00Z"
    },
    "gpu": {
      "slot": "gpu",
      "title": "NVIDIA GeForce RTX 5060 16GB",
      "sku_source": "backup",
      "is_backup": true,
      "availability_status": "in_stock",
      "vendor": "scan",
      "checked_at": "2026-09-21T11:30:00Z"
    }
  }
}
```

**Shop Usage**:
```javascript
// Before showing "Add to Cart"
const availability = await fetch(`/api/public/curated-availability/build/${buildId}?check_live=true`);

if (!availability.is_available) {
  // Hide "Add to Cart", show "Out of Stock"
  return;
}

if (availability.using_backup_count > 0) {
  // Show info banner: "Some components have been substituted with compatible alternatives"
  showBackupSubstitutionBanner(availability.backup_slots);
}
```

#### `GET /api/public/curated-availability/available-builds`

Get list of currently available builds.

**Query Params**:
- `segment` (optional) - Filter by customer type
- `tier` (optional) - Filter by tier
- `check_live` (bool) - Check live availability

**Response**:
```json
{
  "available_builds": ["FF-GVG-01", "FF-GVG-02", "FF-HPG-01"],
  "count": 3,
  "checked_live": false
}
```

#### `GET /api/public/curated-availability/out-of-stock`

Get list of builds currently out of stock.

**Response**:
```json
{
  "out_of_stock_builds": ["FF-AIW-03", "FF-SWD-03"],
  "count": 2
}
```

### Admin Endpoints (Auth Required)

#### `POST /api/admin/curated-availability/refresh-all`

Refresh availability for all builds.

**Query Params**:
- `check_live` (bool, default=true)

**Response**:
```json
{
  "success": true,
  "total_builds": 24,
  "available": 22,
  "out_of_stock": 2,
  "availability_map": {
    "FF-GVG-01": true,
    "FF-GVG-02": true,
    "FF-AIW-03": false
  }
}
```

#### `GET /api/admin/curated-availability/build/{build_id}/skus`

Get all SKUs (primary + backups) for a build.

**Query Params**:
- `component_slot` (optional) - Filter by slot

**Response**:
```json
[
  {
    "id": 1,
    "component_slot": "gpu",
    "is_primary": true,
    "priority": 0,
    "component_title": "AMD Radeon RX 9060 XT 16GB",
    "availability_status": "out_of_stock",
    "estimated_stock_level": 0,
    "preferred_vendor": "overclockers",
    "vendor_sku": "GX-123-RX",
    "is_active": true
  },
  {
    "id": 2,
    "component_slot": "gpu",
    "is_primary": false,
    "priority": 1,
    "component_title": "NVIDIA GeForce RTX 5060 16GB",
    "availability_status": "in_stock",
    "estimated_stock_level": 8,
    "preferred_vendor": "scan",
    "vendor_sku": "LN12345",
    "is_active": true
  }
]
```

#### `POST /api/admin/curated-availability/build/{build_id}/add-backup-sku`

Add a backup SKU for a component slot.

**Request**:
```json
{
  "build_id": "FF-GVG-02",
  "component_slot": "gpu",
  "component_title": "NVIDIA GeForce RTX 5060 16GB",
  "priority": 1,
  "preferred_vendor": "scan",
  "vendor_sku": "LN12345",
  "vendor_url": "https://scan.co.uk/...",
  "target_cost_gbp": 349.99,
  "requires_approval_for_swap": true,
  "requires_remesh": true
}
```

#### `POST /api/admin/curated-availability/build/{build_id}/swap-sku`

Manually swap a component SKU.

**Request**:
```json
{
  "build_id": "FF-GVG-02",
  "component_slot": "gpu",
  "to_sku_id": 2,
  "reason": "primary_out_of_stock",
  "notes": "Primary GPU OOS, swapping to backup RTX 5060"
}
```

#### `GET /api/admin/curated-availability/build/{build_id}/swap-history`

Get SKU swap history.

**Response**:
```json
{
  "build_id": "FF-GVG-02",
  "swaps": [
    {
      "id": 5,
      "component_slot": "gpu",
      "swap_reason": "out_of_stock",
      "swap_source": "system",
      "approved_by": null,
      "swapped_at": "2026-09-21T10:15:00Z"
    }
  ],
  "count": 1
}
```

#### `POST /api/admin/curated-availability/sku/{sku_id}/deactivate`

Deactivate a SKU (mark as no longer usable).

**Request**:
```json
{
  "reason": "Component discontinued by manufacturer"
}
```

#### `POST /api/admin/curated-availability/sku/{sku_id}/check-availability`

Force availability check for a specific SKU.

**Query Params**:
- `force_refresh` (bool, default=true)

---

## Shop Integration

### Before Adding to Cart

```typescript
// Check availability before allowing purchase
const checkAvailability = async (buildId: string) => {
  const response = await fetch(
    `/api/public/curated-availability/build/${buildId}?check_live=true`
  );
  const availability = await response.json();
  
  if (!availability.is_available) {
    showOutOfStockMessage();
    return false;
  }
  
  if (availability.using_backup_count > 0) {
    showBackupSubstitutionNotice(availability.components);
  }
  
  return true;
};
```

### Analytics Tagging

```typescript
// Tag order with SKU sources
const tagOrderWithSKUSources = (availability: BuildAvailability) => {
  const skuSources = {};
  
  for (const [slot, component] of Object.entries(availability.components)) {
    skuSources[slot] = component.sku_source; // "primary" or "backup"
  }
  
  trackEvent({
    event_type: "order_created",
    curated_build_id: availability.build_id,
    metadata: {
      sku_sources: skuSources,
      using_backup_count: availability.using_backup_count
    }
  });
};
```

### UI Components

**Backup Substitution Banner**:
```tsx
{availability.using_backup_count > 0 && (
  <div className="bg-blue-50 border-l-4 border-blue-400 p-4">
    <div className="flex">
      <InfoIcon className="text-blue-400" />
      <div className="ml-3">
        <p className="text-sm text-blue-700">
          <strong>Component Substitution:</strong> {availability.using_backup_count} 
          component{availability.using_backup_count > 1 ? 's have' : ' has'} been 
          substituted with a compatible alternative due to availability.
        </p>
        <p className="text-xs text-blue-600 mt-1">
          Affected: {availability.backup_slots.join(', ')}
        </p>
      </div>
    </div>
  </div>
)}
```

---

## BuildBot Integration

### Providing Primary + Backup SKUs

BuildBot should stamp playbooks with primary + backup SKUs in approval queue:

```json
{
  "build_id": "FF-GVG-02",
  "bot_approval_queue_id": 123,
  "components": [
    {
      "slot": "gpu",
      "primary": {
        "title": "AMD Radeon RX 9060 XT 16GB",
        "vendor": "overclockers",
        "vendor_sku": "GX-123-RX",
        "vendor_url": "https://...",
        "target_cost_gbp": 399.99
      },
      "backups": [
        {
          "title": "NVIDIA GeForce RTX 5060 16GB",
          "vendor": "scan",
          "vendor_sku": "LN12345",
          "vendor_url": "https://...",
          "target_cost_gbp": 349.99,
          "requires_approval_for_swap": true,
          "requires_remesh": true,
          "compatibility_notes": {
            "performance_delta": "-8%",
            "power_delta": "-20W",
            "tested": true
          }
        }
      ]
    }
  ]
}
```

### Compatibility Matrix

BuildBot owns the compatibility matrix. Backup SKUs must be:
- ✅ Performance-compatible (within acceptable range)
- ✅ Power-compatible (PSU can handle it)
- ✅ Physical-compatible (fits in case)
- ✅ Feature-compatible (meets use case requirements)

---

## Analytics Requirements

### Order Tagging

Every order must include `sku_source` for each component:

```json
{
  "order_id": 12345,
  "curated_build_id": "FF-GVG-02",
  "sku_sources": {
    "cpu": "primary",
    "motherboard": "primary",
    "ram": "primary",
    "gpu": "backup",  // ← Backup used here
    "storage": "primary",
    "case": "primary",
    "psu": "primary",
    "cooling": "primary",
    "os": "primary"
  },
  "using_backup_count": 1,
  "backup_slots": ["gpu"]
}
```

### Funnel Events

Track backup usage in funnel:

```json
{
  "event_type": "playbook_viewed",
  "curated_build_id": "FF-GVG-02",
  "metadata": {
    "using_backup_count": 1,
    "backup_slots": ["gpu"],
    "primary_oos_slots": ["gpu"]
  }
}
```

---

## Approval Flow

### Permanent BOM Replacements

Temporary (soft) swaps don't require approval. Permanent replacements do.

**Temporary Swap** (automatic, no approval):
- Primary temporarily OOS
- Swap to backup automatically
- Swap back to primary when stock returns
- No approval needed

**Permanent Replacement** (requires Michael approval):
- Component discontinued
- Better alternative found
- Price permanently changed
- Requires approval in /approvals
- MeshyBot remesh if visible part

### Visible Parts

Parts that require MeshyBot remesh:
- Case (always)
- GPU (if visible through glass panel)
- CPU cooler (if RGB or visible)
- RAM (if RGB or visible)

Parts that don't require remesh:
- Motherboard (usually hidden)
- Storage (always hidden)
- PSU (usually hidden)
- OS (software)

---

## Migration & Rollout

### Phase 1: Data Model & API

- [x] Create database tables (migration 20260921_0003)
- [x] Implement availability service
- [x] Add public + admin API endpoints
- [ ] Populate initial SKU data (primary + backups from BuildBot)

### Phase 2: Vendor Integrations

- [ ] Implement OverclockersChecker
- [ ] Implement ScanChecker
- [ ] Implement AmazonChecker
- [ ] Test live availability checks

### Phase 3: Shop Integration

- [ ] Update build detail page to check availability
- [ ] Add backup substitution banner
- [ ] Disable "Add to Cart" when OOS
- [ ] Hide tiers/ships when all SKUs OOS

### Phase 4: Analytics Integration

- [ ] Tag orders with sku_source
- [ ] Track funnel events with backup usage
- [ ] Dashboard for backup usage metrics

---

## Database Migrations

Run migrations:
```bash
cd flipflop-api
alembic upgrade head
```

Creates:
- `curated_component_skus` table
- `curated_build_availability` table
- `sku_swap_events` table

---

## Testing

### Manual Testing

```bash
# Add primary + backup SKUs for a build
curl -X POST http://localhost:18000/api/admin/curated-availability/build/FF-GVG-02/add-backup-sku \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "build_id": "FF-GVG-02",
    "component_slot": "gpu",
    "component_title": "NVIDIA GeForce RTX 5060 16GB",
    "priority": 1,
    "preferred_vendor": "scan",
    "vendor_sku": "LN12345"
  }'

# Check build availability
curl http://localhost:18000/api/public/curated-availability/build/FF-GVG-02?check_live=true

# Refresh all builds
curl -X POST http://localhost:18000/api/admin/curated-availability/refresh-all \
  -H "Authorization: Bearer <admin-token>"
```

---

## Future Enhancements

1. **Predictive Swaps**: Swap to backup proactively when primary stock is low
2. **Price-Based Swaps**: Swap to cheaper backup when price delta is favorable
3. **Multi-Vendor Fallback**: Check multiple vendors for primary before swapping
4. **Stock Forecasting**: Use swap history to predict future OOS events
5. **Automated Alerts**: Notify team when frequent swaps indicate supply issues

---

## Related Documentation

- [Curated Promotion Guide](./CURATED_PROMOTION_GUIDE.md)
- [Ship Naming Implementation](./SHIP_NAMING_AND_LISTING_PACKS_IMPLEMENTATION.md)
- [Auth & Buying Flow](./AUTH_AND_BUYING_FLOW_IMPLEMENTATION.md)

---

**Status**: Ready for BuildBot integration and vendor checker implementation.
