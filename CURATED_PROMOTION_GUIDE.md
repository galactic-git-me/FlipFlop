# Curated Set Promotion Guide: Dev → Production

**Status**: 🏗️ Ready for use  
**Branch**: `cursor/curated-playbooks-storefront-13ea`

## Overview

This document describes the **dev → production promotion path** for the curated FlipFlop set, allowing Michael's approval clicks in dev to flow to production (andromeda-ts) without re-clicking the entire catalogue.

### Design Goals

1. **Dev sign-off only**: Michael's current Approve clicks are dev sign-off. After promote, only new/changed SKUs go through /approvals again.
2. **No re-clicks**: Approved playbooks, pricing, photo packs, and 3D assets promote together.
3. **Safe promotion**: Export/import with dry-run validation and environment verification.
4. **Tracked history**: All promotions logged in `curated_promotions` table.
5. **Bot updates to prod**: BuildBot/PricingBot/MeshyBot daily updates write directly to prod admin after first promotion.

---

## What Gets Promoted

### 1. Curated Playbooks
- **Source**: `data/curated_build_definitions.json` (24 builds: FF-GVG-01 through FF-FAM-03)
- **Includes**: Component specs, segment, tier, use case descriptions
- **Approval**: All 24 playbooks approved in dev (bot approval queue ids 122-145)

### 2. Ship Names
- **Source**: `tmp/ship-name-map.json` (BuildBot stamped, ids 122-145)
- **Includes**: `display_name`, `ship_name`, `segment`, `tier`, `bespoke_consult` flag
- **Config**: `data/ship_names.json` (ship metadata: series, descriptions)

### 3. Pricing
- **Source**: Bot approval queue ids 66-89 (provisional sells + upsell deltas)
- **Includes**: Sell prices, production costs, delta_sell for upsells
- **Referenced by**: `bot_approval_queue_id` in ship_name_map.json

### 4. Photo Packs (Pending)
- **Source**: TBD (awaiting MeshyBot approval)
- **Includes**: ~15 images per playbook (spec coverage, performance, 3D rendered stills)
- **Note**: Scaffolded in promotion manifest, implementation pending

### 5. 3D Assets (Pending)
- **Source**: TBD (awaiting MeshyBot `.glb` generation)
- **Includes**: Case + component `.glb` files for 3D configurator
- **Note**: Scaffolded in promotion manifest, implementation pending

---

## Promotion Workflow

### Step 1: Export from Dev

**Run on dev environment** (local machine or dev server):

```bash
cd flipflop-api
python scripts/promote_curated_to_production.py export --output ./curated-promotion-manifest.json --promoted-by michael@theflipflop.shop
```

**What it does**:
- Loads curated_build_definitions.json (24 playbooks)
- Loads ship-name-map.json (BuildBot stamped names, ids 122-145)
- Loads ship_names.json (ship metadata)
- References pricing (bot approval queue ids 66-89)
- Creates promotion manifest with SHA256 hash for verification
- Records export in `curated_promotions` table

**Output**: `curated-promotion-manifest.json` with structure:
```json
{
  "version": "1.0",
  "promoted_at": "2026-09-21T11:30:00Z",
  "promoted_by": "michael@theflipflop.shop",
  "source_environment": "dev",
  "target_environment": "production",
  "playbooks_count": 24,
  "pricing_count": 24,
  "photo_packs_count": 0,
  "assets_3d_count": 0,
  "manifest_hash": "a3f5b2c8d1e9f7a2",
  "data": {
    "playbooks": { "builds": [...], "ship_names": {...}, "ship_config": {...} },
    "pricing": { "items": [...] },
    "photo_packs": { "packs": [] },
    "assets_3d": { "assets": [] }
  }
}
```

### Step 2: Transfer Manifest to Production

**Copy manifest to andromeda-ts**:

```bash
# From local dev machine to andromeda-ts
scp curated-promotion-manifest.json andromeda:/home/mac/FlipFlop/
```

Or use the admin API (if available):
```bash
# Upload via admin API
curl -X POST https://www.theflipflop.shop/api/admin/curated-promotion/export \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{"include_playbooks": true, "include_pricing": true}'
```

### Step 3: Dry-Run Import on Production

**⚠️ ALWAYS RUN DRY-RUN FIRST!**

**Run on andromeda-ts**:

```bash
cd /home/mac/FlipFlop/flipflop-api
python scripts/promote_curated_to_production.py import \
  --manifest ../curated-promotion-manifest.json \
  --dry-run
```

**What it does**:
- Verifies manifest hash integrity
- Checks target environment is production (APP_ENV=production or FLIPFLOP_RUNTIME_ENV=live)
- Validates playbooks data structure
- Checks file paths and permissions
- **Does NOT apply any changes**

**Output**:
```
🔍 DRY RUN MODE - No changes will be applied

Manifest: ../curated-promotion-manifest.json
Target: production (andromeda-ts)

Environment check:
  - APP_ENV: production
  - FLIPFLOP_RUNTIME_ENV: live

Pre-import checks:
  ✅ manifest_integrity: PASS
  ✅ environment: is_production=True

Applied changes:
  ✅ playbooks: 24 imported, 0 skipped
      Note: DRY RUN: Would import curated_build_definitions.json and ship naming data
  ✅ pricing: 24 imported, 0 skipped
      Note: DRY RUN: Would import pricing references
  ✅ photo_packs: 0 imported, 0 skipped
      Note: DRY RUN: Photo packs pending implementation
  ✅ assets_3d: 0 imported, 0 skipped
      Note: DRY RUN: 3D assets pending implementation

✅ Dry-run validation passed!

Next step:
  Apply to production: python scripts/promote_curated_to_production.py import --manifest ../curated-promotion-manifest.json --no-dry-run
```

### Step 4: Apply to Production

**⚠️ ONLY after dry-run passes and you've verified the manifest!**

**Run on andromeda-ts**:

```bash
cd /home/mac/FlipFlop/flipflop-api
python scripts/promote_curated_to_production.py import \
  --manifest ../curated-promotion-manifest.json \
  --no-dry-run
```

**Interactive confirmation**:
```
⚠️  LIVE MODE - Changes will be applied to production!

Are you sure you want to proceed? Type 'yes' to continue: yes
```

**What it does**:
- All dry-run checks
- Writes `data/curated_build_definitions.json` to production
- Writes `tmp/ship-name-map.json` to production
- Writes `data/ship_names.json` to production
- Records import in `curated_promotions` table with status="completed"
- Triggers storefront cache refresh (if applicable)

**Result**: Curated builds immediately available on FlipFlop.shop production!

---

## Safety Features

### 1. Dry-Run Mode (Default)
- Always defaults to dry-run
- Must explicitly pass `--no-dry-run` to apply changes
- Validates all operations before applying

### 2. Environment Verification
- Checks `APP_ENV=production` or `FLIPFLOP_RUNTIME_ENV=live`
- Refuses to apply changes if not on production
- Can be bypassed with `verify_environment=false` (not recommended)

### 3. Manifest Hash Verification
- SHA256 hash computed on export
- Verified on import to detect corruption/tampering
- Import fails if hash doesn't match

### 4. Interactive Confirmation
- Requires typing "yes" to proceed with live import
- Displays environment details before applying
- Second chance to abort

### 5. Audit Trail
- All promotions logged in `curated_promotions` table
- Includes: promoted_by, timestamp, manifest snapshot, status
- View history via admin API or database

---

## Admin API Endpoints

### Export Curated Set

```http
POST /api/admin/curated-promotion/export
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "include_playbooks": true,
  "include_pricing": true,
  "include_photo_packs": true,
  "include_3d_assets": true,
  "notes": "Initial promotion after dev approval"
}
```

**Response**:
```json
{
  "success": true,
  "promotion_id": 1,
  "manifest": { ... },
  "message": "Curated set exported successfully. Use /import with dry_run=true to preview, then dry_run=false to apply."
}
```

### Import Curated Set (Dry-Run)

```http
POST /api/admin/curated-promotion/import
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "manifest_path": "/path/to/manifest.json",
  "dry_run": true,
  "verify_environment": true,
  "notes": "Dry-run validation before production apply"
}
```

**Response**:
```json
{
  "success": true,
  "dry_run": true,
  "result": {
    "checks": { "manifest_integrity": "PASS", "environment": {...} },
    "applied": { "playbooks": {...}, "pricing": {...} },
    "errors": []
  },
  "message": "DRY RUN: No changes applied"
}
```

### Import Curated Set (Live)

```http
POST /api/admin/curated-promotion/import
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "manifest": { ... },  // Or use manifest_path
  "dry_run": false,
  "verify_environment": true,
  "notes": "Production apply after dry-run validation"
}
```

### View Promotion History

```http
GET /api/admin/curated-promotion/history?limit=50&offset=0
Authorization: Bearer <admin-token>
```

**Response**:
```json
[
  {
    "id": 1,
    "promoted_at": "2026-09-21T11:30:00Z",
    "promoted_by": "michael@theflipflop.shop",
    "source_environment": "dev",
    "target_environment": "production",
    "playbooks_count": 24,
    "pricing_count": 24,
    "photo_packs_count": 0,
    "assets_3d_count": 0,
    "status": "completed",
    "notes": "Initial promotion"
  }
]
```

### Get Promotion Details

```http
GET /api/admin/curated-promotion/{promotion_id}
Authorization: Bearer <admin-token>
```

### Rollback Promotion

```http
POST /api/admin/curated-promotion/{promotion_id}/rollback
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "reason": "Bad pricing data, reverting to previous state"
}
```

**Note**: Rollback only marks the record - manual reversion or re-import of previous state required.

---

## Database Schema

### `curated_promotions` Table

```sql
CREATE TABLE curated_promotions (
    id INTEGER PRIMARY KEY,
    promoted_at TIMESTAMP NOT NULL,
    promoted_by VARCHAR(255) NOT NULL,
    source_environment VARCHAR(50) NOT NULL DEFAULT 'dev',
    target_environment VARCHAR(50) NOT NULL DEFAULT 'production',
    
    promotion_manifest JSON NOT NULL,
    
    playbooks_count INTEGER NOT NULL DEFAULT 0,
    pricing_count INTEGER NOT NULL DEFAULT 0,
    photo_packs_count INTEGER NOT NULL DEFAULT 0,
    assets_3d_count INTEGER NOT NULL DEFAULT 0,
    
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    verification_checks JSON,
    
    import_result JSON,
    import_error TEXT,
    
    rolled_back_at TIMESTAMP,
    rolled_back_by VARCHAR(255),
    rollback_reason TEXT,
    
    notes TEXT,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
```

---

## File Locations

### Dev Environment (Local)
```
flipflop-api/
├── data/
│   ├── curated_build_definitions.json  # 24 playbooks
│   └── ship_names.json                 # Ship metadata
├── tmp/
│   └── ship-name-map.json              # BuildBot stamped (ids 122-145)
└── scripts/
    └── promote_curated_to_production.py
```

### Production Environment (andromeda-ts)
```
/home/mac/FlipFlop/
└── flipflop-api/
    ├── data/
    │   ├── curated_build_definitions.json  # ← Promoted here
    │   └── ship_names.json                 # ← Promoted here
    ├── tmp/
    │   └── ship-name-map.json              # ← Promoted here
    └── scripts/
        └── promote_curated_to_production.py
```

---

## Bot Workflow After Promotion

### BuildBot
- **Dev**: Continues to stamp playbooks with `display_name` (approval queue ids 122+)
- **Prod**: Daily updates write directly to prod admin after first promotion
- **New SKUs**: Go through /approvals in prod if not in manifest

### PricingBot
- **Dev**: Continues to approve pricing (approval queue ids 66+)
- **Prod**: Daily price updates write directly to prod admin
- **New SKUs**: Go through /approvals in prod if not in manifest

### MeshyBot
- **Dev**: Generates `.glb` files, awaits approval
- **Prod**: After first promotion, approved `.glb`s sync directly to prod
- **New models**: Go through /approvals in prod if not in manifest

---

## Troubleshooting

### Import Fails: "Not production environment"

**Symptom**:
```
⚠️ Not production environment: app_env=dev, runtime_env=development
```

**Solution**:
- Verify you're on andromeda-ts: `hostname` should show andromeda-ts
- Check environment variables:
  ```bash
  echo $APP_ENV         # Should be "production"
  echo $FLIPFLOP_RUNTIME_ENV  # Should be "live"
  ```
- Ensure `.env.local` on andromeda has production settings

### Import Fails: "Manifest hash mismatch"

**Symptom**:
```
❌ Manifest hash mismatch: expected a3f5b2c8, got f7a2d1e9
```

**Solution**:
- Manifest was corrupted during transfer
- Re-export from dev and transfer again
- Verify file integrity: `sha256sum curated-promotion-manifest.json`

### Playbooks Not Appearing on Storefront

**Symptom**: Promotion succeeded but builds not showing on FlipFlop.shop

**Solution**:
- Check API is reading the promoted files:
  ```bash
  curl https://www.theflipflop.shop/api/public/curated-builds | jq
  ```
- Verify file paths on andromeda-ts:
  ```bash
  ls -lh /home/mac/FlipFlop/flipflop-api/data/curated_build_definitions.json
  ls -lh /home/mac/FlipFlop/flipflop-api/tmp/ship-name-map.json
  ```
- Restart API if needed:
  ```bash
  cd /home/mac/FlipFlop
  docker compose -f deploy/andromeda-api.compose.yml restart api
  ```

### Permission Denied Writing Files

**Symptom**:
```
❌ Failed to write curated_build_definitions.json: Permission denied
```

**Solution**:
- Ensure script runs as correct user (same as API process)
- Check file permissions:
  ```bash
  ls -ld /home/mac/FlipFlop/flipflop-api/data
  ls -ld /home/mac/FlipFlop/flipflop-api/tmp
  ```
- Fix permissions if needed:
  ```bash
  sudo chown -R mac:mac /home/mac/FlipFlop/flipflop-api/data
  sudo chown -R mac:mac /home/mac/FlipFlop/flipflop-api/tmp
  ```

---

## Future Enhancements

### 1. Automated Promotion Pipeline
- GitHub Actions workflow: dev merge → auto-export → staging → prod
- Slack notifications on promotion success/failure
- Automatic rollback on failure

### 2. Incremental Promotions
- Only promote changed playbooks/pricing (delta exports)
- Versioning for each playbook (track changes over time)
- Diff view in admin: what changed since last promotion

### 3. Photo Pack & 3D Asset Sync
- Implement when MeshyBot integration completes
- Sync `.glb` files from dev to production S3/storage
- Validate 3D assets before promotion

### 4. Rollback Automation
- Store previous state with each promotion
- One-click rollback to last known good state
- A/B testing: promote to 50% of traffic first

---

## Related Documentation

- [Ship Naming Implementation](./SHIP_NAMING_AND_LISTING_PACKS_IMPLEMENTATION.md)
- [Shared Card Services Architecture](./SHARED_CARD_SERVICES_ARCHITECTURE.md)
- [Auth & Buying Flow](./AUTH_AND_BUYING_FLOW_IMPLEMENTATION.md)
- [Production-to-Local Sync](./docs/PRODUCTION_TO_LOCAL_SYNC.md)
- [Deployment Guide](./docs/DEPLOYMENT_GUIDE.md)

---

## Summary

**Dev → Production Promotion Path**:
1. ✅ Export from dev (curated playbooks + ship names + pricing refs)
2. ✅ Transfer manifest to andromeda-ts
3. ✅ Dry-run import (ALWAYS first!)
4. ✅ Apply to production (after verification)
5. ✅ Curated builds live on FlipFlop.shop

**Key Benefits**:
- Michael's dev approvals flow to production without re-clicking
- Safe promotion with dry-run and environment verification
- Full audit trail in database
- Bots write directly to prod after first promotion
- Only new/changed SKUs require re-approval

**Status**: Ready for use with current 24 curated playbooks (ids 122-145).
