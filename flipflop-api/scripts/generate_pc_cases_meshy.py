"""Generate 5 PC case 3D models with Meshy AI with textures."""
from __future__ import annotations

import asyncio
import httpx
import structlog
from pathlib import Path
import sys
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.database import AsyncSessionLocal, engine
from app.models.case import Case
from app.services.media_sync import sync_to_public_media

log = structlog.get_logger(__name__)

_MESHY_BASE = "https://api.meshy.ai/openapi/v2/text-to-3d"
_POLL_INTERVAL_SECONDS = 5
_MAX_POLL_ATTEMPTS = 120

CASES_TO_GENERATE = [
    {
        "name": "ATX Full Tower Gaming Case",
        "form_factors": ["ATX"],
        "keywords": ["gaming", "full-tower", "RGB", "tempered-glass"],
        "prompt": "a large full-tower ATX desktop PC case with tempered glass side panel, RGB lighting strips, multiple fan mounts, no branding or logos"
    },
    {
        "name": "Compact Mini ITX Case",
        "form_factors": ["ITX"],
        "keywords": ["compact", "mini-ITX", "portable", "aluminum"],
        "prompt": "a compact mini-ITX desktop PC case with aluminum frame and tempered glass, single 120mm fan mount, clean minimalist design, no branding"
    },
    {
        "name": "Mid Tower Mesh Front Case",
        "form_factors": ["ATX", "MATX"],
        "keywords": ["mid-tower", "mesh", "airflow", "gaming"],
        "prompt": "a mid-tower ATX desktop PC case with full mesh front panel for airflow, tempered glass side panel, three 120mm fan mount points, no branding"
    },
    {
        "name": "Horizontal SFF Case",
        "form_factors": ["MATX"],
        "keywords": ["small-form-factor", "horizontal", "compact"],
        "prompt": "a horizontal small-form-factor desktop PC case with tempered glass, MATX motherboard support, clean modern design, no branding or logos"
    },
    {
        "name": "High-Airflow Tower Case",
        "form_factors": ["ATX"],
        "keywords": ["airflow", "tower", "gaming", "cooling"],
        "prompt": "a tall tower desktop PC case with large mesh front panel, multiple 120mm and 140mm fan mounts, tempered glass side panel, RGB fans, no branding"
    },
]


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {"Authorization": f"Bearer {settings.meshy_api_key}", "Content-Type": "application/json"}


async def generate_case(case_data: dict) -> dict | None:
    """Generate a textured 3D case model with Meshy."""
    settings = get_settings()
    if not settings.meshy_api_key:
        log.warning("meshy_generation.no_api_key")
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            print(f"\nGENERATING: {case_data['name']}")
            submit = await client.post(
                _MESHY_BASE,
                headers=_headers(),
                json={
                    "mode": "preview",
                    "prompt": case_data["prompt"],
                    "art_style": "realistic",
                    "should_remesh": True,
                    "should_texture": True,
                    "enable_pbr": True,
                },
            )
            submit.raise_for_status()
            task_id = submit.json().get("result")
            if not task_id:
                print(f"FAILED: No task ID returned")
                return None

            print(f"   Task ID: {task_id}")
    except httpx.HTTPError as exc:
        print(f"SUBMIT FAILED: {exc}")
        return None

    for attempt in range(_MAX_POLL_ATTEMPTS):
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                poll = await client.get(f"{_MESHY_BASE}/{task_id}", headers=_headers())
                poll.raise_for_status()
                data = poll.json()
        except httpx.HTTPError as exc:
            print(f"   Polling... (attempt {attempt + 1})")
            continue

        status = data.get("status", "")
        if status == "SUCCEEDED":
            model_urls = data.get("model_urls") or {}
            glb_url = model_urls.get("glb")
            print(f"GENERATED: {case_data['name']}")
            return {
                "case_data": case_data,
                "task_id": task_id,
                "glb_url": glb_url,
                "thumbnail_url": data.get("thumbnail_url"),
            }
        elif status in ("FAILED", "CANCELED"):
            print(f"MESHY FAILED: {status}")
            return None
        else:
            if attempt % 12 == 0:  # Log every 60 seconds
                print(f"   Polling... status={status} (attempt {attempt + 1}/120)")

    print(f"TIMED OUT after {_MAX_POLL_ATTEMPTS * _POLL_INTERVAL_SECONDS}s")
    return None


async def download_and_store(result: dict, db_session) -> Case | None:
    """Download the GLB and store in database."""
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            glb_response = await client.get(result["glb_url"])
            glb_response.raise_for_status()
            glb_bytes = glb_response.content

        case_data = result["case_data"]
        filename = f"case-{case_data['name'].lower().replace(' ', '-')}-{result['task_id'][:8]}.glb"

        # Store locally
        media_path = Path(__file__).resolve().parents[2] / "FlipFlop.shop" / "public" / "media" / filename
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(glb_bytes)

        # Sync to remote
        await sync_to_public_media(media_path)

        glb_url = f"https://theflipflop.shop/media/{filename}"
        print(f"   Downloaded & synced: {filename}")

        # Create database record
        case = Case(
            name=case_data["name"],
            form_factors=case_data["form_factors"],
            keywords=case_data["keywords"],
            source_site="meshy_ai",
            has_3d_model=True,
            model_3d_url=glb_url,
            model_3d_source="meshy_ai",
            model_3d_creator="Meshy AI",
            model_3d_quality="high",
            status="completed",
        )
        db_session.add(case)
        await db_session.flush()
        print(f"   Saved to database: Case #{case.id}")
        return case

    except Exception as exc:
        print(f"   DOWNLOAD/STORE FAILED: {exc}")
        return None


async def main():
    """Generate 5 PC case models."""
    print("\n" + "="*60)
    print("GENERATING 5 PC CASE 3D MODELS WITH MESHY")
    print("="*60)

    async with AsyncSessionLocal() as db:
        results = []

        # Generate all 5 cases with slight delays to avoid rate limiting
        for i, case_data in enumerate(CASES_TO_GENERATE):
            if i > 0:
                await asyncio.sleep(2)  # Stagger requests

            result = await generate_case(case_data)
            if result:
                case = await download_and_store(result, db)
                if case:
                    results.append(case)
                    await db.commit()
            else:
                await db.rollback()

    await engine.dispose()

    print("\n" + "="*60)
    print(f"COMPLETE: Generated {len(results)}/5 cases")
    print("="*60 + "\n")

    for case in results:
        print(f"  OK {case.name} (ID: {case.id})")


if __name__ == "__main__":
    asyncio.run(main())
