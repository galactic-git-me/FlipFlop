# Meshy Asset Storage Guide

**Problem:** Meshy CDN URLs expire after a period of time. If FlipFlop.shop or the personalised portal links directly to these URLs, the 3D models will break.

**Solution:** Download `.glb` files from Meshy and store them locally in `flipflop-api/app/data/uploads/3d-assets/`, then serve them via stable public URLs.

---

## Architecture

### Storage Location

All 3D assets are stored under:
```
flipflop-api/app/data/uploads/3d-assets/{category}/{filename}.glb
```

This directory is served via FastAPI at:
```
/api/uploads/3d-assets/{category}/{filename}.glb
```

**Example:**
- Physical path: `flipflop-api/app/data/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb`
- Public URL: `/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb`

### Database Integration

The `Component3DAsset` model stores:
- `glb_ref`: Public URL to the locally-stored `.glb` file
- `preview_image_ref`: Public URL to the preview image (if available)
- `file_size_kb`: File size in KB
- `status`: Asset lifecycle status (MISSING, MESHY_DRAFT, CLEANED, VALIDATED, FINAL, REJECTED)

### Filename Generation

Filenames are generated deterministically based on asset attributes:
```
{subject_type}_{subject_id}_{category}_{family_key}_v{version}_{hash}.glb
```

**Example:**
```
case_123_case_v1_a3f5b2c8.glb
variant_456_gpu_gpu_large_triple_fan_v2_b7d9e3f1.glb
```

---

## API Endpoints

### Admin API (requires authentication)

All endpoints are under `/api/admin/meshy-assets/` and require admin authentication.

#### 1. Download Single Asset

**POST** `/api/admin/meshy-assets/download`

Download a single `.glb` file from Meshy and store locally.

**Request Body:**
```json
{
  "asset_id": 123,
  "meshy_glb_url": "https://cdn.meshy.ai/tasks/abc123/output.glb",
  "meshy_preview_url": "https://cdn.meshy.ai/tasks/abc123/preview.png",
  "force_redownload": false,
  "update_status": true,
  "new_status": "meshy_draft"
}
```

**Response:**
```json
{
  "success": true,
  "asset_id": 123,
  "glb_url": "/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb",
  "preview_url": "/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8_preview.png",
  "message": "Asset downloaded and stored successfully"
}
```

**Use Cases:**
- After Michael approves a 3D asset in admin
- When preparing assets for production promotion
- When Meshy URL is about to expire

---

#### 2. Batch Download Assets

**POST** `/api/admin/meshy-assets/batch-download`

Download multiple assets in one operation.

**Request Body:**
```json
{
  "assets": [
    {
      "asset_id": 123,
      "meshy_glb_url": "https://cdn.meshy.ai/tasks/abc123/output.glb",
      "meshy_preview_url": "https://cdn.meshy.ai/tasks/abc123/preview.png"
    },
    {
      "asset_id": 124,
      "meshy_glb_url": "https://cdn.meshy.ai/tasks/def456/output.glb"
    }
  ],
  "force_redownload": false
}
```

**Response:**
```json
{
  "success": true,
  "total": 2,
  "successful": [
    {
      "asset_id": 123,
      "glb_url": "/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb",
      "preview_url": "/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8_preview.png"
    },
    {
      "asset_id": 124,
      "glb_url": "/api/uploads/3d-assets/gpu/variant_124_gpu_v1_c8f2a9d3.glb",
      "preview_url": null
    }
  ],
  "failed": []
}
```

---

#### 3. Download from Approval Queue

**POST** `/api/admin/meshy-assets/download-from-approval`

Download asset directly from approval queue payload.

**Request Body:**
```json
{
  "asset_id": 123,
  "approval_payload": {
    "meshy_glb_url": "https://cdn.meshy.ai/tasks/abc123/output.glb",
    "meshy_preview_url": "https://cdn.meshy.ai/tasks/abc123/preview.png",
    "bot_approval_queue_id": 145
  }
}
```

**Response:**
```json
{
  "success": true,
  "asset_id": 123,
  "glb_url": "/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb",
  "preview_url": "/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8_preview.png",
  "message": "Asset downloaded from approval queue"
}
```

---

#### 4. Check Asset Status

**GET** `/api/admin/meshy-assets/{asset_id}/status`

Check if an asset needs to be downloaded.

**Response:**
```json
{
  "asset_id": 123,
  "needs_download": true,
  "current_glb_ref": "https://cdn.meshy.ai/tasks/abc123/output.glb",
  "is_meshy_url": true,
  "status": "meshy_draft",
  "reason": "glb_ref is Meshy CDN URL (will expire)"
}
```

---

#### 5. Check All Meshy URLs

**GET** `/api/admin/meshy-assets/check-all-meshy-urls?limit=100`

Find all assets still pointing to Meshy CDN URLs.

**Response:**
```json
{
  "total_checked": 50,
  "meshy_urls": 12,
  "local_urls": 38,
  "needs_download": [
    {
      "asset_id": 123,
      "subject_type": "case",
      "subject_id": 45,
      "category": "case",
      "glb_ref": "https://cdn.meshy.ai/tasks/abc123/output.glb",
      "status": "meshy_draft"
    },
    {
      "asset_id": 124,
      "subject_type": "variant",
      "subject_id": 789,
      "category": "gpu",
      "glb_ref": "https://cdn.meshy.ai/tasks/def456/output.glb",
      "status": "validated"
    }
  ]
}
```

---

## Workflows

### Workflow 1: On Approval of 3D Asset

When Michael approves a 3D asset in the admin approval queue:

1. **Admin UI calls download endpoint:**
   ```javascript
   POST /api/admin/meshy-assets/download-from-approval
   {
     "asset_id": 123,
     "approval_payload": {
       "meshy_glb_url": "...",
       "meshy_preview_url": "...",
       "bot_approval_queue_id": 145
     }
   }
   ```

2. **Service downloads and stores:**
   - Downloads `.glb` from Meshy URL
   - Stores in `data/uploads/3d-assets/{category}/`
   - Updates `Component3DAsset.glb_ref` to local URL
   - Updates `Component3DAsset.preview_image_ref`
   - Updates status to `MESHY_DRAFT`

3. **Asset is now safe:**
   - Local storage prevents expiration issues
   - Shop and portal can reference stable URL
   - Asset ready for production promotion

---

### Workflow 2: Dev → Production Promotion

When promoting curated assets to production:

1. **Export from dev:**
   ```bash
   python scripts/promote_curated_to_production.py export
   ```
   
   - Exports 3D asset metadata (only local URLs, not Meshy URLs)
   - Creates manifest: `tmp/curated_promotion_manifest_YYYYMMDD_HHMMSS.json`

2. **Transfer files:**
   ```bash
   # Copy manifest
   scp tmp/curated_promotion_manifest_20260921_120000.json prod:/workspace/flipflop-api/tmp/
   
   # Rsync 3D assets directory
   rsync -avz app/data/uploads/3d-assets/ prod:/workspace/flipflop-api/app/data/uploads/3d-assets/
   ```

3. **Import to production:**
   ```bash
   # On production
   python scripts/promote_curated_to_production.py import \
     --manifest tmp/curated_promotion_manifest_20260921_120000.json \
     --no-dry-run
   ```
   
   - Imports asset metadata into production database
   - `.glb` files already copied via rsync
   - Assets immediately available at same URLs

---

### Workflow 3: Admin Dashboard - Check for Expired URLs

Periodic check to find assets that still point to Meshy:

1. **Admin UI calls:**
   ```javascript
   GET /api/admin/meshy-assets/check-all-meshy-urls
   ```

2. **Response shows expiring assets:**
   ```json
   {
     "meshy_urls": 5,
     "needs_download": [...]
   }
   ```

3. **Batch download all:**
   ```javascript
   POST /api/admin/meshy-assets/batch-download
   {
     "assets": [
       {"asset_id": 123, "meshy_glb_url": "...", "meshy_preview_url": "..."},
       {"asset_id": 124, "meshy_glb_url": "...", "meshy_preview_url": "..."}
     ]
   }
   ```

---

## Service Layer

### `MeshyAssetDownloader` Class

Located in `app/services/meshy_asset_downloader.py`.

#### Key Methods

**`download_and_store_asset()`**
- Downloads `.glb` and preview from Meshy
- Generates stable filename
- Stores in local directory
- Updates database with local URL
- Returns public URLs

**`batch_download_assets()`**
- Downloads multiple assets efficiently
- Handles failures gracefully
- Returns success/failure map

**`download_from_approval_queue()`**
- Extracts Meshy URLs from approval payload
- Downloads and stores
- Updates asset status

**`is_meshy_url()`**
- Checks if URL points to Meshy CDN
- Used to identify assets needing download

---

## Integration Points

### 1. Admin Approval Flow

When approval queue item is approved:
```python
from app.services.meshy_asset_downloader import download_and_store_meshy_asset

# On approval
local_glb_url, local_preview_url = await download_and_store_meshy_asset(
    db,
    asset_id=123,
    meshy_glb_url=approval_payload["meshy_glb_url"],
    meshy_preview_url=approval_payload.get("meshy_preview_url")
)
```

### 2. Curated Promotion Export

Export only includes assets with local storage:
```python
# In CuratedPromotionService._export_3d_assets()
assets = db.query(Component3DAsset).filter(
    Component3DAsset.status.in_([
        Component3DAssetStatus.VALIDATED,
        Component3DAssetStatus.FINAL
    ]),
    Component3DAsset.glb_ref.isnot(None),
    # Exclude Meshy URLs
    ~Component3DAsset.glb_ref.like('%meshy%')
).all()
```

### 3. Shop / Portal Usage

Always use `glb_ref` from database:
```typescript
// FlipFlop.shop
const glbUrl = build.glb_ref;  // /api/uploads/3d-assets/case/...

<model-viewer
  src={glbUrl}
  ar
  camera-controls
/>
```

### 4. Admin Approvals Viewer

Proxy Meshy URLs until approved, then switch to local:
```typescript
// Before approval: proxy through /glb-proxy
const previewUrl = `/glb-proxy?url=${encodeURIComponent(meshyUrl)}`;

// After approval: use local storage
const previewUrl = asset.glb_ref;
```

---

## File Size Management

### Monitoring

Track file sizes in database:
```sql
SELECT 
  category,
  COUNT(*) as asset_count,
  SUM(file_size_kb) as total_kb,
  AVG(file_size_kb) as avg_kb
FROM component_3d_assets
WHERE glb_ref IS NOT NULL
GROUP BY category;
```

### Cleanup

Remove old versions:
```sql
-- Keep only active versions
DELETE FROM component_3d_assets
WHERE is_active = FALSE
  AND status = 'rejected'
  AND created_at < NOW() - INTERVAL '90 days';
```

---

## Security & Access Control

### Admin-Only Downloads

All download endpoints require admin authentication:
```python
@router.post("/download")
async def download_asset(
    request: DownloadAssetRequest,
    admin_email: str = Depends(get_current_admin),  # Auth required
    db: AsyncSession = Depends(get_db)
):
    ...
```

### Public Asset Serving

Assets are served publicly via `/api/uploads/`:
- No authentication required for viewing
- CORS headers enabled for configurator
- Direct URL access allowed

This is intentional - the storefront and personalised portal need public access to display 3D models.

---

## Troubleshooting

### Problem: Asset not appearing in shop

**Check:**
1. Is `glb_ref` set in database?
   ```sql
   SELECT id, glb_ref FROM component_3d_assets WHERE id = 123;
   ```

2. Does file exist on disk?
   ```bash
   ls -lh app/data/uploads/3d-assets/case/
   ```

3. Is asset status approved?
   ```sql
   SELECT status, review_decision FROM component_3d_assets WHERE id = 123;
   ```

**Fix:**
```bash
# Re-download if needed
curl -X POST http://localhost:18000/api/admin/meshy-assets/download \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"asset_id": 123, "meshy_glb_url": "...", "force_redownload": true}'
```

---

### Problem: Promotion failed for 3D assets

**Check:**
1. Were `.glb` files copied via rsync?
   ```bash
   # On production
   ls -lh app/data/uploads/3d-assets/
   ```

2. Does import show errors?
   ```bash
   python scripts/promote_curated_to_production.py import \
     --manifest tmp/manifest.json \
     --dry-run
   ```

**Fix:**
```bash
# Re-copy files
rsync -avz dev:/workspace/flipflop-api/app/data/uploads/3d-assets/ \
  /workspace/flipflop-api/app/data/uploads/3d-assets/

# Re-run import
python scripts/promote_curated_to_production.py import \
  --manifest tmp/manifest.json \
  --no-dry-run
```

---

### Problem: File size too large

**Check:**
```sql
SELECT id, file_size_kb, poly_count 
FROM component_3d_assets 
WHERE file_size_kb > 5000;
```

**Fix:**
1. Mark asset for cleanup/optimization
2. Request MeshyBot regenerate with lower poly count
3. Use Blender to optimize manually
4. Update asset with cleaned version

---

## Best Practices

### 1. Always Download After Approval

Never leave Meshy URLs in production database:
```python
# BAD - leaves Meshy URL
asset.glb_ref = meshy_url
await db.commit()

# GOOD - downloads and stores locally
glb_url, preview_url = await download_and_store_meshy_asset(
    db, asset_id, meshy_url, meshy_preview_url
)
```

### 2. Verify Before Promotion

Check all assets have local storage:
```bash
curl http://localhost:18000/api/admin/meshy-assets/check-all-meshy-urls
```

If any Meshy URLs found, download them before promoting.

### 3. Backup Asset Files

Include `data/uploads/3d-assets/` in backups:
```bash
# Daily backup
tar -czf 3d-assets-backup-$(date +%Y%m%d).tar.gz \
  app/data/uploads/3d-assets/
```

### 4. Monitor Disk Usage

Track growth over time:
```bash
du -sh app/data/uploads/3d-assets/
```

Consider cleanup policies for rejected/old assets.

### 5. Test Assets After Download

Verify `.glb` files are valid:
```bash
# Check file is not corrupted
file app/data/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb

# Verify size is reasonable
ls -lh app/data/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb
```

---

## Future Enhancements

### 1. CDN Integration

When ready for scale, integrate with CDN:
- Upload to S3/CloudFlare R2
- Update `glb_ref` to CDN URL
- Keep local copy as backup

### 2. Automatic Cleanup

Implement lifecycle policies:
- Archive rejected assets after 90 days
- Compress old versions
- Auto-delete duplicates

### 3. Preview Generation

Generate thumbnail previews automatically:
- Use Playwright + Three.js
- Create 256x256 PNG thumbnails
- Store alongside `.glb` files

### 4. Compression Pipeline

Optimize assets before storage:
- Draco compression for `.glb`
- Texture resizing
- LOD generation

---

## Quick Reference

### Download Single Asset
```bash
curl -X POST http://localhost:18000/api/admin/meshy-assets/download \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": 123,
    "meshy_glb_url": "https://cdn.meshy.ai/tasks/abc/output.glb",
    "meshy_preview_url": "https://cdn.meshy.ai/tasks/abc/preview.png"
  }'
```

### Check for Expired URLs
```bash
curl http://localhost:18000/api/admin/meshy-assets/check-all-meshy-urls
```

### Batch Download
```bash
curl -X POST http://localhost:18000/api/admin/meshy-assets/batch-download \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "assets": [
      {"asset_id": 123, "meshy_glb_url": "...", "meshy_preview_url": "..."},
      {"asset_id": 124, "meshy_glb_url": "...", "meshy_preview_url": "..."}
    ]
  }'
```

### Promote with Assets
```bash
# 1. Export
python scripts/promote_curated_to_production.py export

# 2. Copy files
rsync -avz app/data/uploads/3d-assets/ prod:app/data/uploads/3d-assets/

# 3. Import
python scripts/promote_curated_to_production.py import \
  --manifest tmp/manifest.json \
  --no-dry-run
```
