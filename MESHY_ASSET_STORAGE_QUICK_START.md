# Meshy Asset Storage - Quick Start

**TL;DR:** Meshy CDN URLs expire. Download and store `.glb` files locally to avoid broken 3D models.

---

## Problem

```
❌ FlipFlop.shop → Meshy CDN URL → EXPIRES → 3D model breaks
```

## Solution

```
✅ FlipFlop.shop → Local storage URL → /api/uploads/3d-assets/... → Always works
```

---

## For Michael: After Approving 3D Asset

### Option 1: Admin UI (TODO - when built)

1. Click "Download & Store" button in approval queue
2. Asset automatically downloaded from Meshy
3. Stored in local uploads directory
4. Database updated with stable URL

### Option 2: API Call

```bash
curl -X POST http://localhost:18000/api/admin/meshy-assets/download-from-approval \
  -H "Authorization: Bearer $YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": 123,
    "approval_payload": {
      "meshy_glb_url": "https://cdn.meshy.ai/tasks/abc123/output.glb",
      "meshy_preview_url": "https://cdn.meshy.ai/tasks/abc123/preview.png"
    }
  }'
```

**Result:**
```json
{
  "success": true,
  "glb_url": "/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb",
  "message": "Asset downloaded and stored successfully"
}
```

---

## For Developers: Using Assets in Code

### Frontend (FlipFlop.shop / Personalised Portal)

Always use `glb_ref` from the database:

```typescript
// ✅ GOOD - uses stable local URL
const glbUrl = build.glb_ref;  // "/api/uploads/3d-assets/case/..."

<model-viewer
  src={glbUrl}
  ar
  camera-controls
/>
```

```typescript
// ❌ BAD - direct Meshy URL will expire
const glbUrl = "https://cdn.meshy.ai/tasks/abc123/output.glb";
```

### Backend (flipflop-api)

Download Meshy assets after approval:

```python
from app.services.meshy_asset_downloader import download_and_store_meshy_asset

# On asset approval
glb_url, preview_url = await download_and_store_meshy_asset(
    db,
    asset_id=123,
    meshy_glb_url=meshy_response["output_url"],
    meshy_preview_url=meshy_response.get("preview_url")
)

# glb_url is now: "/api/uploads/3d-assets/case/..."
# Safe to store in database and use permanently
```

---

## Check for Expired URLs

Find assets still pointing to Meshy:

```bash
curl http://localhost:18000/api/admin/meshy-assets/check-all-meshy-urls
```

**Response:**
```json
{
  "meshy_urls": 5,
  "needs_download": [
    {
      "asset_id": 123,
      "category": "case",
      "glb_ref": "https://cdn.meshy.ai/tasks/abc/output.glb",
      "reason": "glb_ref is Meshy CDN URL (will expire)"
    }
  ]
}
```

**Fix:**
```bash
# Batch download all
curl -X POST http://localhost:18000/api/admin/meshy-assets/batch-download \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assets": [
      {"asset_id": 123, "meshy_glb_url": "...", "meshy_preview_url": "..."},
      {"asset_id": 124, "meshy_glb_url": "...", "meshy_preview_url": "..."}
    ]
  }'
```

---

## Dev → Production Promotion

### 1. Export (on dev)
```bash
python scripts/promote_curated_to_production.py export
```

### 2. Copy files (dev → prod)
```bash
# Copy manifest
scp tmp/curated_promotion_manifest_*.json prod:/workspace/flipflop-api/tmp/

# Copy 3D assets
rsync -avz app/data/uploads/3d-assets/ \
  prod:/workspace/flipflop-api/app/data/uploads/3d-assets/
```

### 3. Import (on prod)
```bash
python scripts/promote_curated_to_production.py import \
  --manifest tmp/curated_promotion_manifest_20260921_120000.json \
  --no-dry-run
```

**Important:** Always rsync the `.glb` files separately. The import only handles database metadata.

---

## File Locations

### Local Storage
```
flipflop-api/app/data/uploads/3d-assets/
├── case/
│   ├── case_123_case_v1_a3f5b2c8.glb
│   └── case_123_case_v1_a3f5b2c8_preview.png
├── gpu/
│   └── variant_456_gpu_large_triple_fan_v1_b7d9e3f1.glb
└── cooling/
    └── variant_789_cooling_v1_c8f2a9d3.glb
```

### Public URLs
```
/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb
/api/uploads/3d-assets/gpu/variant_456_gpu_large_triple_fan_v1_b7d9e3f1.glb
/api/uploads/3d-assets/cooling/variant_789_cooling_v1_c8f2a9d3.glb
```

---

## Troubleshooting

### Asset not showing in shop?

1. **Check database:**
   ```sql
   SELECT id, glb_ref, status FROM component_3d_assets WHERE id = 123;
   ```

2. **Check file exists:**
   ```bash
   ls -lh app/data/uploads/3d-assets/case/
   ```

3. **Re-download if needed:**
   ```bash
   curl -X POST http://localhost:18000/api/admin/meshy-assets/download \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"asset_id": 123, "meshy_glb_url": "...", "force_redownload": true}'
   ```

### Promotion failed?

1. **Check files were copied:**
   ```bash
   # On prod
   ls -lh app/data/uploads/3d-assets/
   ```

2. **Re-copy if missing:**
   ```bash
   rsync -avz dev:app/data/uploads/3d-assets/ app/data/uploads/3d-assets/
   ```

3. **Re-run import:**
   ```bash
   python scripts/promote_curated_to_production.py import \
     --manifest tmp/manifest.json \
     --no-dry-run
   ```

---

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/admin/meshy-assets/download` | POST | Download single asset |
| `/api/admin/meshy-assets/batch-download` | POST | Download multiple assets |
| `/api/admin/meshy-assets/download-from-approval` | POST | Download from approval queue |
| `/api/admin/meshy-assets/{id}/status` | GET | Check if asset needs download |
| `/api/admin/meshy-assets/check-all-meshy-urls` | GET | Find all expired URLs |

All require admin authentication.

---

## Best Practices

✅ **DO:**
- Download assets immediately after approval
- Use `glb_ref` from database in frontend
- Verify all assets have local storage before promotion
- Include `data/uploads/3d-assets/` in backups
- Check for Meshy URLs periodically

❌ **DON'T:**
- Store Meshy CDN URLs in production database
- Link directly to Meshy URLs in shop/portal
- Skip rsync step during promotion
- Delete old assets without checking if they're active
- Assume Meshy URLs will work forever

---

## Reference

- **Full Guide:** `MESHY_ASSET_STORAGE_GUIDE.md`
- **Service:** `flipflop-api/app/services/meshy_asset_downloader.py`
- **API:** `flipflop-api/app/api/meshy_asset_downloader.py`
- **Promotion:** `CURATED_PROMOTION_GUIDE.md`
