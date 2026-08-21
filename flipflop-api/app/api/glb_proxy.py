"""Proxy GLB files from local storage for 3D viewer. Avoids CORS and remote storage issues."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/glb-proxy", tags=["glb-proxy"])

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
MEDIA_ROOT = WORKSPACE_ROOT.parent / "FlipFlop.shop" / "public" / "media"


@router.get("/{filename}")
async def get_glb(filename: str):
    """Serve GLB file by filename for 3D viewer (CORS-safe)."""
    # Safety: only allow catalogue 3d files
    if not filename.startswith("catalogue-3d-") or not filename.endswith(".glb"):
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = MEDIA_ROOT / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"GLB file not found: {filename}")

    return FileResponse(
        file_path,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )
