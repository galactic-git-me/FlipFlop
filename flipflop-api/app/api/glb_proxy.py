"""Proxy for loading GLB files from external URLs with CORS support."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import httpx

router = APIRouter(prefix="/glb-proxy", tags=["glb-proxy"])


@router.get("")
async def proxy_glb(url: str):
    """Proxy GLB file from external URL."""
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter required")

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            return StreamingResponse(
                iter([response.content]),
                media_type="model/gltf-binary",
                headers={"Access-Control-Allow-Origin": "*"}
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch GLB: {exc}")
