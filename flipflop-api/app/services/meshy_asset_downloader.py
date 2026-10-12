"""
Meshy Asset Downloader Service.

Downloads .glb files (and previews) from Meshy CDN and stores them locally to avoid
expired URLs.

Design:
- On approval of model-3d (or as part of promote):
  1. Download .glb from Meshy URL
  2. Store under data/uploads/3d-assets/{category}/{filename}.glb
  3. Update asset record with stable local URL
  4. Shop/portal/listings use stored file

- Admin approvals viewer may proxy Meshy until approved, then switch to stored path
- Supports both single asset downloads and batch operations
- Handles filename collisions with versioning
"""
import httpx
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.component_3d_asset import Component3DAsset, Component3DAssetStatus

log = get_logger(__name__)


class MeshyAssetDownloader:
    """Service for downloading and storing Meshy 3D assets locally."""
    
    def __init__(self, db: AsyncSession, base_upload_dir: Path):
        self.db = db
        self.base_upload_dir = base_upload_dir
        self.assets_dir = base_upload_dir / "3d-assets"
        self.assets_dir.mkdir(parents=True, exist_ok=True)
    
    async def download_and_store_asset(
        self,
        asset_id: int,
        meshy_glb_url: str,
        meshy_preview_url: Optional[str] = None,
        force_redownload: bool = False
    ) -> Tuple[str, Optional[str]]:
        """
        Download .glb (and preview) from Meshy and store locally.
        
        Args:
            asset_id: Component3DAsset ID
            meshy_glb_url: Meshy CDN URL for .glb file
            meshy_preview_url: Meshy CDN URL for preview image (optional)
            force_redownload: Force re-download even if local file exists
            
        Returns:
            (glb_local_url, preview_local_url) - Local URLs (relative to /api/uploads/)
        """
        # Get asset record
        stmt = select(Component3DAsset).where(Component3DAsset.id == asset_id)
        result = await self.db.execute(stmt)
        asset = result.scalar_one_or_none()
        
        if not asset:
            raise ValueError(f"Asset {asset_id} not found")
        
        log.info(
            "meshy_asset.download_start",
            asset_id=asset_id,
            subject_type=asset.subject_type.value if asset.subject_type else None,
            subject_id=asset.subject_id
        )
        
        # Determine storage paths
        category = asset.category or "generic"
        subject_type = asset.subject_type.value if asset.subject_type else "unknown"
        
        # Create subdirectory for this asset category
        category_dir = self.assets_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename based on asset details
        filename_base = self._generate_filename(asset)
        
        # Download .glb file
        glb_filename = f"{filename_base}.glb"
        glb_local_path = category_dir / glb_filename
        
        if force_redownload or not glb_local_path.exists():
            await self._download_file(meshy_glb_url, glb_local_path)
            log.info("meshy_asset.glb_downloaded", path=str(glb_local_path), size_bytes=glb_local_path.stat().st_size)
        else:
            log.info("meshy_asset.glb_exists", path=str(glb_local_path))
        
        # Generate public URL (relative to /api/uploads/)
        glb_public_url = f"/api/uploads/3d-assets/{category}/{glb_filename}"
        
        # Download preview image if provided
        preview_public_url = None
        if meshy_preview_url:
            # Detect preview image extension from URL or content-type
            preview_ext = self._detect_extension(meshy_preview_url, default=".png")
            preview_filename = f"{filename_base}_preview{preview_ext}"
            preview_local_path = category_dir / preview_filename
            
            if force_redownload or not preview_local_path.exists():
                await self._download_file(meshy_preview_url, preview_local_path)
                log.info("meshy_asset.preview_downloaded", path=str(preview_local_path))
            else:
                log.info("meshy_asset.preview_exists", path=str(preview_local_path))
            
            preview_public_url = f"/api/uploads/3d-assets/{category}/{preview_filename}"
        
        # Update asset record with local paths
        asset.glb_ref = glb_public_url
        if preview_public_url:
            asset.preview_image_ref = preview_public_url
        
        # Update file metadata
        glb_size_kb = int(glb_local_path.stat().st_size / 1024)
        asset.file_size_kb = glb_size_kb
        
        await self.db.commit()
        
        log.info(
            "meshy_asset.download_complete",
            asset_id=asset_id,
            glb_url=glb_public_url,
            preview_url=preview_public_url,
            size_kb=glb_size_kb
        )
        
        return glb_public_url, preview_public_url
    
    async def _download_file(self, url: str, destination: Path):
        """Download file from URL to local path."""
        try:
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                # Write to file
                destination.write_bytes(response.content)
                
                log.info(
                    "meshy_asset.file_downloaded",
                    url=url,
                    destination=str(destination),
                    size_bytes=len(response.content)
                )
                
        except httpx.HTTPError as e:
            log.error("meshy_asset.download_failed", url=url, error=str(e))
            raise RuntimeError(f"Failed to download {url}: {e}")
    
    def _generate_filename(self, asset: Component3DAsset) -> str:
        """
        Generate stable filename for asset based on its attributes.
        
        Format: {subject_type}_{subject_id}_{category}_{version}_{hash}
        Example: case_123_case_1_a3f5b2c8
        """
        parts = []
        
        if asset.subject_type:
            parts.append(asset.subject_type.value)
        
        if asset.subject_id:
            parts.append(str(asset.subject_id))
        
        if asset.category:
            parts.append(asset.category)
        
        if asset.family_key:
            # Sanitize family_key for filesystem
            sanitized_key = asset.family_key.replace("/", "_").replace(" ", "_")
            parts.append(sanitized_key)
        
        parts.append(f"v{asset.version}")
        
        # Add short hash of asset ID + created_at for uniqueness
        hash_input = f"{asset.id}_{asset.created_at.isoformat() if asset.created_at else datetime.utcnow().isoformat()}"
        hash_short = hashlib.md5(hash_input.encode()).hexdigest()[:8]
        parts.append(hash_short)
        
        return "_".join(parts)
    
    def _detect_extension(self, url: str, default: str = ".png") -> str:
        """Detect file extension from URL."""
        url_lower = url.lower()
        
        if ".png" in url_lower:
            return ".png"
        elif ".jpg" in url_lower or ".jpeg" in url_lower:
            return ".jpg"
        elif ".webp" in url_lower:
            return ".webp"
        elif ".gif" in url_lower:
            return ".gif"
        
        return default
    
    async def batch_download_assets(
        self,
        meshy_url_asset_map: dict[int, Tuple[str, Optional[str]]],
        force_redownload: bool = False
    ) -> dict[int, Tuple[str, Optional[str]]]:
        """
        Batch download multiple assets.
        
        Args:
            meshy_url_asset_map: Map of asset_id -> (glb_url, preview_url)
            force_redownload: Force re-download
            
        Returns:
            Map of asset_id -> (local_glb_url, local_preview_url)
        """
        results = {}
        
        for asset_id, (glb_url, preview_url) in meshy_url_asset_map.items():
            try:
                local_urls = await self.download_and_store_asset(
                    asset_id,
                    glb_url,
                    preview_url,
                    force_redownload
                )
                results[asset_id] = local_urls
            except Exception as e:
                log.error(
                    "meshy_asset.batch_download_failed",
                    asset_id=asset_id,
                    error=str(e)
                )
                results[asset_id] = (None, None)
        
        log.info(
            "meshy_asset.batch_download_complete",
            total=len(meshy_url_asset_map),
            successful=sum(1 for v in results.values() if v[0] is not None),
            failed=sum(1 for v in results.values() if v[0] is None)
        )
        
        return results
    
    async def download_from_approval_queue(
        self,
        asset_id: int,
        approval_payload: dict
    ) -> Tuple[str, Optional[str]]:
        """
        Download asset from approval queue payload.
        
        Approval payload should contain:
        - meshy_glb_url: Meshy CDN URL for .glb
        - meshy_preview_url: Meshy CDN URL for preview (optional)
        
        Args:
            asset_id: Component3DAsset ID
            approval_payload: Approval queue payload with Meshy URLs
            
        Returns:
            (local_glb_url, local_preview_url)
        """
        glb_url = approval_payload.get("meshy_glb_url")
        preview_url = approval_payload.get("meshy_preview_url")
        
        if not glb_url:
            raise ValueError("No meshy_glb_url in approval payload")
        
        return await self.download_and_store_asset(
            asset_id,
            glb_url,
            preview_url
        )
    
    async def update_asset_status_after_download(
        self,
        asset_id: int,
        new_status: Component3DAssetStatus = Component3DAssetStatus.MESHY_DRAFT
    ):
        """Update asset status after successful download."""
        stmt = select(Component3DAsset).where(Component3DAsset.id == asset_id)
        result = await self.db.execute(stmt)
        asset = result.scalar_one_or_none()
        
        if asset:
            asset.status = new_status
            await self.db.commit()
            
            log.info(
                "meshy_asset.status_updated",
                asset_id=asset_id,
                status=new_status.value
            )
    
    def get_local_asset_path(self, asset_id: int, category: str, filename: str) -> Path:
        """Get local filesystem path for an asset."""
        return self.assets_dir / category / filename
    
    def is_meshy_url(self, url: str) -> bool:
        """Check if URL is a Meshy CDN URL (will expire)."""
        if not url:
            return False
        
        url_lower = url.lower()
        return "meshy" in url_lower or "cdn.meshy.ai" in url_lower


# Convenience functions for common operations

async def download_and_store_meshy_asset(
    db: AsyncSession,
    asset_id: int,
    meshy_glb_url: str,
    meshy_preview_url: Optional[str] = None,
    base_upload_dir: Optional[Path] = None
) -> Tuple[str, Optional[str]]:
    """
    Download and store a Meshy asset.
    
    Convenience function for single asset download.
    """
    if base_upload_dir is None:
        # Default to app/data/uploads
        from pathlib import Path
        base_upload_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
    
    downloader = MeshyAssetDownloader(db, base_upload_dir)
    return await downloader.download_and_store_asset(
        asset_id,
        meshy_glb_url,
        meshy_preview_url
    )


async def download_meshy_assets_from_approval(
    db: AsyncSession,
    approval_queue_items: list[dict],
    base_upload_dir: Optional[Path] = None
) -> dict[int, Tuple[str, Optional[str]]]:
    """
    Download multiple Meshy assets from approval queue.
    
    Args:
        approval_queue_items: List of approval queue items with:
            - asset_id: Component3DAsset ID
            - meshy_glb_url: Meshy CDN URL
            - meshy_preview_url: Preview URL (optional)
    
    Returns:
        Map of asset_id -> (local_glb_url, local_preview_url)
    """
    if base_upload_dir is None:
        from pathlib import Path
        base_upload_dir = Path(__file__).resolve().parents[1] / "data" / "uploads"
    
    downloader = MeshyAssetDownloader(db, base_upload_dir)
    
    meshy_url_map = {
        item["asset_id"]: (item["meshy_glb_url"], item.get("meshy_preview_url"))
        for item in approval_queue_items
    }
    
    return await downloader.batch_download_assets(meshy_url_map)
