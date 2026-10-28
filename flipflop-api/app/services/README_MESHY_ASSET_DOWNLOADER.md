# Meshy Asset Downloader Service

## Overview

Service for downloading `.glb` 3D model files from Meshy CDN and storing them locally to prevent URL expiration.

## Problem

Meshy CDN URLs expire after a period of time. If FlipFlop.shop or the personalised portal links directly to these URLs, the 3D models will break and users will see missing/broken 3D viewers.

## Solution

1. Download `.glb` (and preview images) from Meshy CDN when asset is approved
2. Store files in `app/data/uploads/3d-assets/{category}/`
3. Update `Component3DAsset.glb_ref` to stable local URL (`/api/uploads/3d-assets/...`)
4. Shop and portal always use `glb_ref` from database (never direct Meshy URLs)

## Usage

### Single Asset Download

```python
from app.services.meshy_asset_downloader import download_and_store_meshy_asset

# After asset approval
glb_url, preview_url = await download_and_store_meshy_asset(
    db,
    asset_id=123,
    meshy_glb_url="https://cdn.meshy.ai/tasks/abc123/output.glb",
    meshy_preview_url="https://cdn.meshy.ai/tasks/abc123/preview.png"
)

# glb_url is now: "/api/uploads/3d-assets/case/case_123_case_v1_a3f5b2c8.glb"
# Safe to use permanently in shop/portal
```

### Batch Download

```python
from app.services.meshy_asset_downloader import MeshyAssetDownloader

downloader = MeshyAssetDownloader(db, base_upload_dir)

meshy_url_map = {
    123: ("https://cdn.meshy.ai/.../output1.glb", "https://cdn.meshy.ai/.../preview1.png"),
    124: ("https://cdn.meshy.ai/.../output2.glb", None)
}

results = await downloader.batch_download_assets(meshy_url_map)
# results[123] = ("/api/uploads/3d-assets/case/...", "/api/uploads/3d-assets/case/..._preview.png")
# results[124] = ("/api/uploads/3d-assets/gpu/...", None)
```

### From Approval Queue

```python
from app.services.meshy_asset_downloader import MeshyAssetDownloader

downloader = MeshyAssetDownloader(db, base_upload_dir)

approval_payload = {
    "meshy_glb_url": "https://cdn.meshy.ai/.../output.glb",
    "meshy_preview_url": "https://cdn.meshy.ai/.../preview.png",
    "bot_approval_queue_id": 145
}

glb_url, preview_url = await downloader.download_from_approval_queue(
    asset_id=123,
    approval_payload=approval_payload
)
```

## API Endpoints

See `/api/admin/meshy-assets/` for admin endpoints:

- `POST /download` - Download single asset
- `POST /batch-download` - Download multiple assets
- `POST /download-from-approval` - Download from approval queue
- `GET /{id}/status` - Check if asset needs download
- `GET /check-all-meshy-urls` - Find all assets with Meshy URLs

All endpoints require admin authentication.

## File Storage

### Storage Path
```
app/data/uploads/3d-assets/
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
```

### Filename Format
```
{subject_type}_{subject_id}_{category}_{family_key}_v{version}_{hash}.glb
```

Example:
- `case_123_case_v1_a3f5b2c8.glb`
- `variant_456_gpu_large_triple_fan_v2_b7d9e3f1.glb`

## Integration with Promotion

### Export (dev)

Only exports assets with local storage (filters out Meshy URLs):

```python
# In CuratedPromotionService._export_3d_assets()
assets = db.query(Component3DAsset).filter(
    Component3DAsset.status.in_([VALIDATED, FINAL, CLEANED]),
    Component3DAsset.glb_ref.isnot(None),
    ~Component3DAsset.glb_ref.like('%meshy%')  # Exclude Meshy URLs
).all()
```

### Transfer (dev → prod)

```bash
# 1. Copy manifest
scp tmp/curated_promotion_manifest_*.json prod:/workspace/flipflop-api/tmp/

# 2. Rsync .glb files
rsync -avz app/data/uploads/3d-assets/ \
  prod:/workspace/flipflop-api/app/data/uploads/3d-assets/
```

### Import (prod)

Imports asset metadata only (`.glb` files already copied):

```python
# Creates/updates Component3DAsset records with local glb_ref paths
# Files must exist on disk (via rsync) for this to work
```

## Workflows

### Workflow 1: On Approval

```
Michael approves asset in admin
    ↓
Admin UI calls POST /api/admin/meshy-assets/download-from-approval
    ↓
Service downloads .glb from Meshy
    ↓
Stores in app/data/uploads/3d-assets/{category}/
    ↓
Updates Component3DAsset.glb_ref = "/api/uploads/3d-assets/..."
    ↓
Updates status to MESHY_DRAFT
    ↓
Asset ready for use (stable URL, won't expire)
```

### Workflow 2: Before Promotion

```
Dev environment has approved assets
    ↓
Check for Meshy URLs: GET /api/admin/meshy-assets/check-all-meshy-urls
    ↓
If any found, batch download: POST /api/admin/meshy-assets/batch-download
    ↓
Verify all have local storage
    ↓
Ready to promote
```

### Workflow 3: Periodic Audit

```
Cron job or manual check
    ↓
GET /api/admin/meshy-assets/check-all-meshy-urls
    ↓
If meshy_urls > 0:
    Extract asset IDs and Meshy URLs
    POST /api/admin/meshy-assets/batch-download
    ↓
Log results
```

## Class Reference

### `MeshyAssetDownloader`

Main service class for downloading and storing assets.

#### Constructor
```python
__init__(db: AsyncSession, base_upload_dir: Path)
```

#### Methods

**`download_and_store_asset()`**
```python
async def download_and_store_asset(
    asset_id: int,
    meshy_glb_url: str,
    meshy_preview_url: Optional[str] = None,
    force_redownload: bool = False
) -> Tuple[str, Optional[str]]
```
Downloads `.glb` and preview from Meshy, stores locally, updates database.

**`batch_download_assets()`**
```python
async def batch_download_assets(
    meshy_url_asset_map: dict[int, Tuple[str, Optional[str]]],
    force_redownload: bool = False
) -> dict[int, Tuple[str, Optional[str]]]
```
Downloads multiple assets in batch.

**`download_from_approval_queue()`**
```python
async def download_from_approval_queue(
    asset_id: int,
    approval_payload: dict
) -> Tuple[str, Optional[str]]
```
Extracts Meshy URLs from approval payload and downloads.

**`is_meshy_url()`**
```python
def is_meshy_url(url: str) -> bool
```
Checks if URL points to Meshy CDN (will expire).

**`update_asset_status_after_download()`**
```python
async def update_asset_status_after_download(
    asset_id: int,
    new_status: Component3DAssetStatus = Component3DAssetStatus.MESHY_DRAFT
)
```
Updates asset status after successful download.

## Convenience Functions

### `download_and_store_meshy_asset()`

```python
async def download_and_store_meshy_asset(
    db: AsyncSession,
    asset_id: int,
    meshy_glb_url: str,
    meshy_preview_url: Optional[str] = None,
    base_upload_dir: Optional[Path] = None
) -> Tuple[str, Optional[str]]
```

Quick single-asset download without instantiating class.

### `download_meshy_assets_from_approval()`

```python
async def download_meshy_assets_from_approval(
    db: AsyncSession,
    approval_queue_items: list[dict],
    base_upload_dir: Optional[Path] = None
) -> dict[int, Tuple[str, Optional[str]]]
```

Batch download from approval queue items.

## Error Handling

### Download Failures

Service handles network errors gracefully:
- HTTP errors logged and raised as `RuntimeError`
- Individual failures in batch don't stop other downloads
- Failed downloads return `(None, None)` in batch results

### File System Errors

- Creates directories automatically if missing
- Handles file write permissions issues
- Logs all errors with structured logging

### Database Errors

- Transactions rolled back on failure
- Asset record not updated if download fails
- Retry safe (idempotent operations)

## Monitoring

### Check for Expired URLs

```bash
curl http://localhost:18000/api/admin/meshy-assets/check-all-meshy-urls
```

### Monitor Disk Usage

```bash
du -sh app/data/uploads/3d-assets/
```

### Query Database

```sql
-- Count assets with local storage
SELECT COUNT(*) FROM component_3d_assets
WHERE glb_ref LIKE '/api/uploads/3d-assets/%';

-- Count assets still on Meshy
SELECT COUNT(*) FROM component_3d_assets
WHERE glb_ref LIKE '%meshy%';

-- Total storage by category
SELECT 
  category,
  COUNT(*) as count,
  SUM(file_size_kb) / 1024 as total_mb
FROM component_3d_assets
WHERE glb_ref LIKE '/api/uploads/3d-assets/%'
GROUP BY category;
```

## Best Practices

### ✅ DO

- Download assets immediately after approval
- Use `glb_ref` from database in frontend code
- Verify all assets have local storage before promotion
- Include `data/uploads/3d-assets/` in backups
- Check for Meshy URLs periodically

### ❌ DON'T

- Store Meshy CDN URLs in production database
- Link directly to Meshy URLs in shop/portal
- Skip rsync step during promotion
- Delete files without checking database references
- Assume Meshy URLs will work forever

## Related Documentation

- **Full Guide:** `/workspace/MESHY_ASSET_STORAGE_GUIDE.md`
- **Quick Start:** `/workspace/MESHY_ASSET_STORAGE_QUICK_START.md`
- **API:** `/workspace/flipflop-api/app/api/meshy_asset_downloader.py`
- **Promotion:** `/workspace/CURATED_PROMOTION_GUIDE.md`
