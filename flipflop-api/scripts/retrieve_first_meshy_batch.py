"""Retrieve the deliberately limited first three Meshy catalogue trials."""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings


TASKS = {
    # Task creation timestamps preserve the initial queue order.
    "cpu_amd": "01a01c8b-e2d9-7662-8c02-35928fc75fa0",
    "cpu_intel": "01a01c8b-e8ff-7726-ab15-55697bd48630",
    "motherboard_atx": "01a01c8b-e68e-7724-9992-1d3381945bdf",
}
API = "https://api.meshy.ai/openapi/v1/multi-image-to-3d"
OUTPUT = Path(__file__).resolve().parents[2] / "assets/3d-models/review/meshy-first-batch"


async def main() -> None:
    key = get_settings().meshy_api_key
    if not key:
        raise RuntimeError("MESHY_API_KEY is not configured")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        for family, task_id in TASKS.items():
            task = (await client.get(f"{API}/{task_id}", headers=headers)).raise_for_status().json()
            if task.get("status") != "SUCCEEDED":
                print(f"SKIP {family}: {task.get('status')}")
                continue
            urls = task.get("model_urls") or {}
            files = {"glb": urls.get("glb"), "png": task.get("thumbnail_url")}
            for extension, url in files.items():
                if not url:
                    continue
                response = (await client.get(url)).raise_for_status()
                path = OUTPUT / f"{family}.{extension}"
                path.write_bytes(response.content)
                print(f"SAVED {path.name} ({len(response.content)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())
