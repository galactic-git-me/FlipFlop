"""Meshy text-to-3D generation for component-family buckets
(component_family_classifier.py's taxonomy) — one generation per bucket,
reused across every catalogue variant that classifies into it, per the
"model each family once, cache forever" strategy agreed 2026-08-13.

Uses Meshy's v2 text-to-3D REST API: submit a prompt, poll until the task
finishes, then return the result GLB URL for the caller to download and
store in this app's own asset pipeline (never re-fetched from Meshy at
request time — see Component3DAsset.glb_ref). Every generation is saved
with status=MESHY_DRAFT and reviewed later, same discipline as the
motherboard-spec AI backfill in motherboard_spec_ai.py.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx
import structlog

from app.config import get_settings
from app.services.model_reference_images import prepare_reference_images, meshy_reference_inputs

log = structlog.get_logger(__name__)

_MESHY_BASE = "https://api.meshy.ai/openapi/v2/text-to-3d"
_MESHY_IMAGE_BASE = "https://api.meshy.ai/openapi/v1/image-to-3d"
_MESHY_MULTI_IMAGE_BASE = "https://api.meshy.ai/openapi/v1/multi-image-to-3d"
_POLL_INTERVAL_SECONDS = 5
_MAX_POLL_ATTEMPTS = 120  # ~10 minutes ceiling — Meshy generations typically finish well inside this


@dataclass
class MeshyGenerationResult:
    task_id: str
    status: str  # SUCCEEDED | FAILED | ...
    glb_url: str | None
    thumbnail_url: str | None
    poly_count: int | None
    progress: int = 0
    error: str | None = None
    reference_image_urls: list[str] | None = None


def _provider_error(response: httpx.Response) -> str:
    try:
        body = response.json()
    except ValueError:
        body = response.text
    if isinstance(body, dict):
        error = body.get("message") or body.get("error") or body.get("detail") or body
    else:
        error = body
    return str(error)[:500]


async def _submit_image_with_capacity_wait(client, endpoint, payload, progress_callback):
    """Retry explicit pending-capacity rejections only; no task was created.

    Never retry network timeouts or uncertain responses: the provider might
    already have accepted those submissions and charged for them.
    """
    for attempt in range(31):
        response = await client.post(endpoint, headers=_headers(), json=payload)
        capacity_full = response.status_code == 429 and "NoMorePendingTasks" in _provider_error(response)
        if not capacity_full or attempt == 30:
            return response
        if progress_callback:
            await progress_callback(0, "QUEUED", None, "Meshy pending-task capacity is full; waiting for a slot.")
        await asyncio.sleep(10)
    raise RuntimeError("Unreachable submission state")


def _task_error(data: dict) -> str | None:
    error = data.get("task_error") or data.get("error")
    if isinstance(error, dict):
        error = error.get("message") or error.get("type") or error
    return str(error)[:500] if error else None


def _headers() -> dict[str, str]:
    settings = get_settings()
    return {"Authorization": f"Bearer {settings.meshy_api_key}", "Content-Type": "application/json"}


async def generate_family_asset(prompt: str) -> MeshyGenerationResult | None:
    """Submits a text-to-3D job and polls it to completion.

    Returns None (never raises) on missing API key or any request failure —
    callers treat this exactly like the other AI-backend services in this
    codebase: "try again later", not a crash. Runs for real minutes (the
    generation itself takes time), so this belongs behind an admin-triggered
    endpoint, not inline in a customer-facing request."""
    settings = get_settings()
    if not settings.meshy_api_key:
        log.warning("meshy_generation.no_api_key")
        return None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            submit = await client.post(
                _MESHY_BASE,
                headers=_headers(),
                json={
                    "mode": "preview",
                    "prompt": prompt,
                    "art_style": "realistic",
                    "should_remesh": True,
                    "should_texture": True,
                    "enable_pbr": True,
                },
            )
            submit.raise_for_status()
            task_id = submit.json().get("result")
            if not task_id:
                log.warning("meshy_generation.no_task_id", response=submit.text[:300])
                return None
    except httpx.HTTPError as exc:
        log.warning("meshy_generation.submit_failed", error=str(exc))
        return None

    last_progress = 0
    for attempt in range(_MAX_POLL_ATTEMPTS):
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                poll = await client.get(f"{_MESHY_BASE}/{task_id}", headers=_headers())
                poll.raise_for_status()
                data = poll.json()
        except httpx.HTTPError as exc:
            log.warning("meshy_generation.poll_failed", attempt=attempt, error=str(exc))
            continue

        status = data.get("status", "")
        if status == "SUCCEEDED":
            model_urls = data.get("model_urls") or {}
            return MeshyGenerationResult(
                task_id=task_id,
                status=status,
                glb_url=model_urls.get("glb"),
                thumbnail_url=data.get("thumbnail_url"),
                poly_count=None,  # Meshy doesn't report this at preview stage; set on review
            )
        if status in ("FAILED", "CANCELED"):
            log.warning("meshy_generation.task_failed", task_id=task_id, status=status)
            return MeshyGenerationResult(task_id=task_id, status=status, glb_url=None, thumbnail_url=None, poly_count=None)
        # PENDING / IN_PROGRESS — keep polling

    log.warning("meshy_generation.timed_out", task_id=task_id)
    return MeshyGenerationResult(task_id=task_id, status="TIMED_OUT", glb_url=None, thumbnail_url=None, poly_count=None)


async def generate_multi_image_asset(
    image_urls: list[str],
    progress_callback: Callable[[int, str, str | None], Awaitable[None]] | None = None,
) -> MeshyGenerationResult | None:
    """Generate one textured GLB from one to four views of the same object.

    A single view uses Meshy's Image-to-3D endpoint. Two to four views use
    Multi-Image-to-3D, with every supplied view also sent as texture guidance.
    """
    settings = get_settings()
    if not settings.meshy_api_key:
        log.warning("meshy_generation.no_api_key", endpoint="image-to-3d" if len(image_urls) == 1 else "multi-image-to-3d")
        return MeshyGenerationResult("", "CONFIGURATION_ERROR", None, None, None, error="MESHY_API_KEY is not configured in the API process")
    if not 1 <= len(image_urls) <= 4:
        raise ValueError("Meshy image generation requires 1 to 4 images")

    try:
        image_urls = await prepare_reference_images(image_urls)
        provider_images = await meshy_reference_inputs(image_urls)
    except ValueError as error:
        return MeshyGenerationResult("", "SOURCE_IMAGES_INVALID", None, None, None, error=str(error))

    is_single_image = len(image_urls) == 1
    endpoint = _MESHY_IMAGE_BASE if is_single_image else _MESHY_MULTI_IMAGE_BASE

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            payload = {
                # Multi-view texture references require Meshy 7.1. Meshy 6
                # supports only one texture image and cannot honor all chosen
                # photos when rebuilding a model.
                "ai_model": "meshy-7.1",
                "should_texture": True,
                "enable_pbr": True,
                # 2K is the right default for the interactive storefront
                # viewer. 4K substantially increases Meshy's processing time
                # and produces a much larger GLB without improving the normal
                # browser viewing experience.
                "texture_resolution": "2k",
                # Meshy's API recommends disabling remesh for maximum quality.
                "should_remesh": False,
                "target_formats": ["glb"],
            }
            if is_single_image:
                payload = {
                    "image_url": provider_images[0],
                    "texture_image_url": provider_images[0],
                    "ai_model": "meshy-7.1",
                    "texture_resolution": "2k",
                    "should_texture": True,
                    "enable_pbr": True,
                    "target_formats": ["glb"],
                }
            else:
                payload["image_urls"] = provider_images
                payload["texture_image_urls"] = provider_images
            response = await _submit_image_with_capacity_wait(client, endpoint, payload, progress_callback)
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                provider_error = _provider_error(response)
                log.warning(
                    "meshy_generation.image_submit_rejected",
                    single_image=is_single_image,
                    status_code=response.status_code,
                    provider_error=provider_error,
                )
                return MeshyGenerationResult("", f"SUBMIT_REJECTED_{response.status_code}", None, None, None, error=provider_error)
            response_data = response.json()
            task_id = response_data.get("result")
            if not task_id:
                provider_error = _provider_error(response)
                log.warning(
                    "meshy_generation.image_submit_missing_task_id",
                    single_image=is_single_image,
                    provider_error=provider_error,
                )
                return MeshyGenerationResult("", "SUBMIT_FAILED", None, None, None, error=provider_error)
    except httpx.HTTPError as exc:
        log.warning("meshy_generation.image_submit_failed", single_image=is_single_image, error=str(exc))
        return MeshyGenerationResult("", "SUBMIT_FAILED", None, None, None, error=str(exc)[:500])

    result = await poll_multi_image_asset(task_id, is_single_image, progress_callback)
    result.reference_image_urls = image_urls
    return result


async def poll_multi_image_asset(
    task_id: str,
    is_single_image: bool,
    progress_callback: Callable[[int, str, str | None], Awaitable[None]] | None = None,
) -> MeshyGenerationResult:
    """Resume polling an existing Meshy image task without submitting a new paid job."""
    endpoint = _MESHY_IMAGE_BASE if is_single_image else _MESHY_MULTI_IMAGE_BASE
    if progress_callback:
        try:
            await progress_callback(0, "SUBMITTED", task_id)
        except Exception as exc:
            log.warning("meshy_generation.progress_callback_failed", error=str(exc))

    last_progress = 0
    for attempt in range(_MAX_POLL_ATTEMPTS):
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{endpoint}/{task_id}", headers=_headers())
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            log.warning("meshy_generation.image_poll_failed", single_image=is_single_image, attempt=attempt, error=str(exc))
            continue
        status = data.get("status", "")
        progress = max(0, min(100, int(data.get("progress") or 0)))
        last_progress = progress
        if progress_callback:
            try:
                await progress_callback(progress, status, task_id)
            except Exception as exc:
                # A status-display write must never cancel the Meshy job.
                log.warning("meshy_generation.progress_callback_failed", error=str(exc))
        if status == "SUCCEEDED":
            model_urls = data.get("model_urls") or {}
            if not model_urls.get("glb"):
                log.warning("meshy_generation.image_succeeded_without_glb", task_id=task_id, response=data)
            return MeshyGenerationResult(
                task_id=task_id,
                status=status,
                glb_url=model_urls.get("glb"),
                thumbnail_url=data.get("thumbnail_url"),
                poly_count=None,
                progress=progress,
            )
        if status in ("FAILED", "CANCELED"):
            error = _task_error(data)
            log.warning("meshy_generation.image_task_failed", single_image=is_single_image, task_id=task_id, status=status, provider_error=error)
            return MeshyGenerationResult(task_id, status, None, None, None, progress, error)
    return MeshyGenerationResult(task_id, "TIMED_OUT", None, None, None, last_progress)


def build_prompt(category: str, family_key: str) -> str:
    """Turns a bucket key into a plain-English prompt. Deliberately generic/
    silhouette-level language — this must never describe a specific branded
    product closely enough to look like an attempt at an exact replica; the
    whole point of the family-bucket strategy is ONE generic shape per
    bucket, not a copy of any particular manufacturer's design."""
    descriptions = {
        "cpu_amd": "a modern desktop computer CPU processor chip, square ceramic package with metal contact pins, no branding",
        "cpu_amd_threadripper": "a large workstation CPU processor package with a broad rectangular heat spreader and dense underside contact pads, no branding",
        "cpu_intel": "a modern desktop computer CPU processor chip, square ceramic package with gold contact pads, no branding",
        "motherboard_atx": "a full-size ATX desktop PC motherboard with CPU socket, four RAM slots, PCIe slots, M.2 heatsink and rear I/O, no branding",
        "motherboard_matx": "a compact micro-ATX desktop PC motherboard with CPU socket, two or four RAM slots, PCIe slots, M.2 heatsink and rear I/O, no branding",
        "gpu_nvidia": "a modern NVIDIA GeForce desktop PC graphics card with a PCIe connector and cooling shroud",
        "gpu_amd": "a modern AMD Radeon desktop PC graphics card with a PCIe connector and cooling shroud",
        "gpu_intel": "a modern Intel Arc desktop PC graphics card with a PCIe connector and cooling shroud",
        "ram_ddr4": "two matched desktop DDR4 memory modules standing side by side with low-profile black heatspreaders",
        "ram_ddr5": "two matched desktop DDR5 memory modules standing side by side with black heatspreaders",
        "gpu_blower": "a desktop PC graphics card with a single blower-style cooling shroud and radial fan, PCIe form factor, no branding",
        "gpu_compact_dual_fan": "a compact desktop PC graphics card with a two-fan cooling shroud, PCIe form factor, no branding",
        "gpu_mid_dual_fan": "a mid-size desktop PC graphics card with a two-fan cooling shroud, PCIe form factor, no branding",
        "gpu_large_triple_fan": "a large flagship desktop PC graphics card with a three-fan cooling shroud, PCIe form factor, no branding",
        "cooling_air_tower": "a desktop PC CPU air tower cooler with heatpipes and a single fan, no branding",
        "cooling_aio_240": "a desktop PC all-in-one liquid CPU cooler with a 240mm radiator and two fans, no branding",
        "cooling_aio_280": "a desktop PC all-in-one liquid CPU cooler with a 280mm radiator and two fans, no branding",
        "cooling_aio_360": "a desktop PC all-in-one liquid CPU cooler with a 360mm radiator and three fans, no branding",
        "cooling_aio_360_lcd": "a desktop PC all-in-one liquid CPU cooler with a 360mm radiator, three fans, and a square LCD display on the pump, no branding",
        "fan_120_plain": "a 120mm desktop PC case fan, plain frame, no RGB, no branding",
        "fan_120_rgb": "a 120mm desktop PC case fan with an RGB lighting ring, no branding",
        "fan_140_plain": "a 140mm desktop PC case fan, plain frame, no RGB, no branding",
        "fan_140_rgb": "a 140mm desktop PC case fan with an RGB lighting ring, no branding",
        "psu_atx_standard": "a standard ATX desktop PC modular power supply, fan grille and rear power socket visible, no cables or branding",
    }
    if family_key in descriptions:
        return descriptions[family_key]

    if family_key.startswith("mobo_"):
        _, brand, form = family_key.split("_", 2)
        form_label = {"atx": "full-size ATX", "matx": "micro-ATX", "itx": "compact mini-ITX"}.get(form, form)
        return f"a {form_label} desktop PC motherboard, generic layout with CPU socket, RAM slots and PCIe slots, no branding or logos"

    if family_key.startswith("ram_"):
        parts = family_key.split("_")
        colour = parts[-1] if parts[-1] in ("black", "white", "rgb") else "black"
        colour_label = "black" if colour == "black" else ("white" if colour == "white" else "black with an RGB light bar")
        brand = parts[1].replace("gskill", "G.Skill").replace("teamgroup", "TeamGroup").title()
        return f"a matched kit of two desktop PC DDR RAM memory modules standing side by side, {brand}-inspired but with no logos or copied markings, tall rectangular heatspreaders, {colour_label}"

    return f"a generic desktop PC {category} component, {family_key.replace('_', ' ')}, no branding"
