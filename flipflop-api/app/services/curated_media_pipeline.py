"""Select one captured physical component photo for a curated Meshy draft.

Local Qwen ranks the existing product photos and verifies the selected image
against the exact catalogue title. The original image is passed to Meshy's
single-image endpoint; no generated views or image edits are made here.
"""
from __future__ import annotations

import io
import json
from typing import Awaitable, Callable
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from app.services.model_selection_service import ModelSelectionError, model_selection_service
from app.services.model_reference_images import original_image_url

_MAX_CANDIDATES = 300
_MAX_SOURCE_BYTES = 12 * 1024 * 1024
_ALLOWED_IMAGE_HOSTS = {
    "m.media-amazon.com",
    "images-na.ssl-images-amazon.com",
    "images-eu.ssl-images-amazon.com",
    "i.ebayimg.com",
}


class MediaPipelineError(RuntimeError):
    pass


def _parse_json(text: str) -> dict:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MediaPipelineError("Local Qwen returned an unreadable photo decision") from exc
    if not isinstance(value, dict):
        raise MediaPipelineError("Local Qwen returned an invalid photo decision")
    return value


async def _review_image(title: str, image_bytes: bytes, content_type: str) -> dict:
    prompt = (
        "Inspect this captured product photo for the exact catalogue item. Return only JSON with keys: "
        "physical_component (boolean), matches_title (boolean), packaging_or_diagram (boolean), "
        "quality (integer 1-5), reason (short string). Only mark physical_component=true when the "
        "actual component hardware is visible, not its retail box, packaging, diagram or an unrelated item. "
        "Set packaging_or_diagram=true if ANY retail box or packaging is visible, even alongside hardware. "
        "Reject accessories or spare parts when the title category expects a complete component. "
        f"Compare visible identity to this exact title: {title}"
    )
    try:
        result = await model_selection_service.complete(
            task="curated component photo selection",
            messages=[{"role": "user", "content": prompt}],
            images=[(image_bytes, content_type)],
            max_tokens=200,
            timeout=60,
            json_mode=True,
            require_vision=True,
            local_only=True,
        )
    except ModelSelectionError as exc:
        raise MediaPipelineError(f"Local Qwen photo review failed: {exc}") from exc

    decision = _parse_json(result.text)
    for key in ("physical_component", "matches_title", "packaging_or_diagram"):
        if not isinstance(decision.get(key), bool):
            raise MediaPipelineError(f"Local Qwen omitted the required {key} decision")
    try:
        decision["quality"] = max(1, min(5, int(decision.get("quality", 1))))
    except (TypeError, ValueError):
        decision["quality"] = 1
    return decision


async def _download_candidates(urls: list[str]) -> list[tuple[str, bytes, str, int]]:
    candidates: list[tuple[str, bytes, str, int]] = []
    seen: set[str] = set()
    async with httpx.AsyncClient(timeout=25, follow_redirects=False) as client:
        for url in urls:
            if len(candidates) >= _MAX_CANDIDATES:
                break
            resolved = original_image_url(url)
            try:
                parsed = urlsplit(resolved)
            except ValueError:
                continue
            if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_IMAGE_HOSTS or parsed.username or parsed.password:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            try:
                response = await client.get(resolved)
                response.raise_for_status()
                content = response.content
                if not content or len(content) > _MAX_SOURCE_BYTES:
                    continue
                with Image.open(io.BytesIO(content)) as image:
                    image.verify()
                    width, height = image.size
                    content_type = Image.MIME.get(image.format or "", "image/jpeg")
                if min(width, height) < 160:
                    continue
                candidates.append((resolved, content, content_type, width * height))
            except (httpx.HTTPError, UnidentifiedImageError, OSError, Image.DecompressionBombError):
                continue
    return candidates


Progress = Callable[[str, int, str | None], Awaitable[None]]


async def select_component_photo(
    *,
    title: str,
    candidate_urls: list[str],
    progress: Progress,
    first_verified: bool = False,
) -> tuple[str, dict]:
    """Return one Qwen-verified original photo URL and its selection evidence."""
    candidates = await _download_candidates(candidate_urls)
    if not candidates:
        raise MediaPipelineError("No supported, full-size captured product photos are available")

    ranked: list[tuple[int, str, dict]] = []
    for index, (url, content, content_type, pixels) in enumerate(candidates, start=1):
        await progress("reviewing_source_photos", min(75, index * 75 // len(candidates)), None)
        decision = await _review_image(title, content, content_type)
        if decision["physical_component"] and decision["matches_title"] and not decision["packaging_or_diagram"]:
            score = decision["quality"] * 100 + min(pixels // 1_000_000, 4) * 5
            ranked.append((score, url, decision))
            if first_verified:
                break
    if not ranked:
        raise MediaPipelineError("Local Qwen could not verify a captured image as the exact physical component")
    ranked.sort(key=lambda item: item[0], reverse=True)
    _score, selected_url, decision = ranked[0]
    await progress("single_photo_selected", 90, None)
    return selected_url, {
        "selection_method": "local_qwen_exact_component_photo_review",
        "selected_source_url": selected_url,
        "source_decision": decision,
        "candidate_count_reviewed": len(candidates),
    }
