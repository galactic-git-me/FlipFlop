"""Claude-assisted screening (PRD §29-30) — identity refinement, bundle
detection, risk interpretation, and reasoning text ONLY. Output is forced
through a tool schema (never parsed from free text — see _OPENROUTER tier)
so malformed output is a schema-validation error, not a regex miss.

Two-stage cost control (PRD §30): the caller (router) only invokes this for
the top `max_candidates_for_deep_research` listings by deterministic score
per scan — see api/gem_radar.py.

Two-tier provider chain: Ollama (local, GPU-accelerated, no rate limits) ->
OpenRouter (cloud fallback, free models, OpenAI-compatible tool-calling).
Ollama handles text-only screening via JSON-mode; most locally-runnable
models lack vision + tool-calling for photo-verification tier.
"""
from __future__ import annotations

import asyncio
import base64
import json
from dataclasses import dataclass

# Ollama is a single local instance that serves requests essentially
# sequentially — it has no autoscaling and no request queue of its own.
# Without a cap here, every listing that falls through OpenRouter's rate
# limit at once (which is the whole point of this fallback path — it fires
# exactly when OpenRouter is already overloaded) would pile onto Ollama
# simultaneously, each queued behind the others well past its own 180s
# per-call timeout instead of actually running in parallel.
#
# margin_verifier.py's background worker also calls this same local Ollama
# instance (its own model, on the same 8GB-VRAM GPU) — it imports and shares
# THIS semaphore rather than defining its own, so the two callers' combined
# concurrent load never exceeds _OLLAMA_CONCURRENCY. Two independent,
# uncoordinated semaphores would each individually respect their own cap
# while still letting claude_screening + margin_verifier stack up to
# 2x that many concurrent calls against the same GPU — which is exactly
# what was observed (99% GPU util, a trivial prompt taking 45s to answer).
_OLLAMA_CONCURRENCY = 2
_ollama_semaphore = asyncio.Semaphore(_OLLAMA_CONCURRENCY)

import httpx
import structlog

from app.config import get_settings, Settings
from app.gem_radar.schemas import ExtractedListing, Identity
from app.services.model_selection_service import model_selection_service

log = structlog.get_logger(__name__)

_ASSESS_TOOL_SCHEMA = {
    "name": "submit_identity_and_risk_assessment",
    "description": "Submit a structured identity/bundle/risk assessment for one listing.",
    "input_schema": {
        "type": "object",
        "properties": {
            "canonical_name": {
                "type": "string",
                "description": "Best-guess full product name (brand + model + key specs), or empty string if genuinely unidentifiable.",
            },
            "canonical_model_id": {
                "type": "string",
                "description": (
                    "A STABLE matching key for this exact product, not a display name. Format: "
                    "'<BRAND> <MODEL>' in uppercase, brand and model number ONLY — no core/thread counts, "
                    "clock speeds, socket names, coolers, 'CPU'/'Processor'/'Desktop' filler words, or "
                    "seller phrasing. The test: two listings for the same real product, worded completely "
                    "differently, must produce the IDENTICAL string here. Examples: 'Intel Core i7-11700T "
                    "LGA1200 Desktop Processor' and 'Intel i7-11700T PC CPU Processor' both -> "
                    "'INTEL I7-11700T'. 'AMD Ryzen 5 5600X 6-Core Socket AM4 CPU' -> 'AMD RYZEN 5 5600X'. "
                    "Empty string if genuinely unidentifiable — never invent one."
                ),
            },
            "identity_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "release_year": {
                "type": ["integer", "null"],
                "description": "The year this product was originally released/launched, from your own knowledge (e.g. RTX 4070 -> 2023). Null if the identity is too ambiguous to know, or genuinely unidentifiable — never guess.",
            },
            "is_bundle": {"type": "boolean"},
            "bundle_components": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Plain-text names of distinct components if this is a multi-item bundle listing.",
            },
            "additional_risk_notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Any risk/trap language you notice in the title that a keyword scan might miss (e.g. unusual phrasing implying a fault).",
            },
            "reasoning_summary": {
                "type": "string",
                "description": "One or two sentences explaining the identity/bundle/risk assessment. Do not mention or estimate any price.",
            },
        },
        "required": ["canonical_name", "canonical_model_id", "identity_confidence", "is_bundle", "reasoning_summary"],
    },
}

_SYSTEM_PROMPT = """You are a product-identity and risk-language assistant for a PC component deal-screening tool.

Your ONLY job for each listing:
1. Refine the product identity (brand, model, key specs) from the title.
2. Produce a STABLE canonical_model_id (brand + exact model number only, uppercase, no filler words) —
   this is a matching key other listings of the same real product must land on identically, regardless
   of how differently their titles are worded. See the tool schema description for the exact format and
   worked examples.
3. Detect whether the listing is a bundle of multiple distinct components.
4. Flag any risk/trap language a simple keyword scan might miss.
5. From your own knowledge (not a lookup you're given), state the year the identified product was
   originally released/launched — null if the identity is too ambiguous to know.
6. Write a one-to-two sentence reasoning summary.

You MUST NOT:
- State, estimate, or imply any price, market value, or "this is worth about £X". Pricing is computed
  deterministically elsewhere from live market data; if you mention a number it will be discarded and
  logged as a policy violation.
- Invent a model number, specification, or release year you cannot support from the title text or your
  own knowledge — leave release_year null rather than guess.
- Treat an auction's current bid as a final price, or an active listing price as a completed sale.

Call the submit_identity_and_risk_assessment tool with your assessment. Do not respond with plain text."""


@dataclass
class ClaudeAssistResult:
    canonical_name: str
    canonical_model_id: str | None
    identity_confidence: float
    release_year: int | None
    is_bundle: bool
    bundle_components: list[str]
    additional_risk_notes: list[str]
    reasoning_summary: str


def _parse_assist_result(data: dict) -> ClaudeAssistResult | None:
    try:
        raw_release_year = data.get("release_year")
        canonical_model_id = str(data.get("canonical_model_id") or "").strip().upper() or None
        return ClaudeAssistResult(
            canonical_name=str(data.get("canonical_name") or ""),
            canonical_model_id=canonical_model_id,
            identity_confidence=max(0.0, min(1.0, float(data.get("identity_confidence") or 0))),
            release_year=int(raw_release_year) if raw_release_year is not None else None,
            is_bundle=bool(data.get("is_bundle", False)),
            bundle_components=[str(c) for c in data.get("bundle_components") or []],
            additional_risk_notes=[str(n) for n in data.get("additional_risk_notes") or []],
            reasoning_summary=str(data.get("reasoning_summary") or ""),
        )
    except (TypeError, ValueError) as exc:
        log.warning("gem_radar.claude_screening.malformed_output", error=str(exc))
        return None


def _build_user_prompt(listing: ExtractedListing, identity: Identity) -> str:
    return (
        f"Title: {listing.title}\n"
        f"Condition (normalised): {listing.condition_normalised}\n"
        f"Deterministic identity guess: brand={identity.brand}, model={identity.model}, "
        f"category={identity.category}, confidence={identity.exact_sku_confidence}\n"
        "Assess identity, bundle status, and risk language for this listing."
    )


async def screen_with_claude(
    listing: ExtractedListing, identity: Identity, max_retries: int = 2
) -> ClaudeAssistResult | None:
    """Returns None (not a fabricated result) if every configured provider
    is unavailable or every attempt fails schema validation — callers must
    fall back to the deterministic-only assessment, never synthesize an
    LLM opinion.

    Provider priority: Ollama (local, fast, GPU) -> OpenRouter (cloud, fallback)
    """
    user_prompt = _build_user_prompt(listing, identity)
    try:
        selected = await model_selection_service.complete(
            task="Gem Radar identity and risk screening",
            messages=[{"role": "user", "content": user_prompt}],
            system_prompt=_SYSTEM_PROMPT + "\n\nReturn one JSON object with keys: canonical_name, canonical_model_id, identity_confidence, release_year, is_bundle, bundle_components, additional_risk_notes, reasoning_summary.",
            max_tokens=512, timeout=180, json_mode=True,
            tools=[_ASSESS_TOOL_SCHEMA], require_tools=True,
            tool_choice={"type": "function", "function": {"name": "submit_identity_and_risk_assessment"}},
        )
        if selected.tool_calls:
            args = selected.tool_calls[0].get("function", {}).get("arguments", {})
            if isinstance(args, str):
                args = json.loads(args)
            return _parse_assist_result(args)
        if selected.text:
            return _parse_assist_result(json.loads(selected.text))
    except Exception as exc:
        log.warning("gem_radar.claude_screening.model_selection_failed", error=str(exc))
    return None


# --- Batched photo/title category verification -----------------------------
#
# Cost-batching without stitching photos into a physical collage: both
# Anthropic and OpenRouter (OpenAI-compatible) natively accept several
# separate images in one message, so a batch of N candidates costs one
# system prompt + one round of output tokens instead of N of each, while
# every photo stays at full resolution. A stitched grid would save the same
# fixed overhead but shrink each photo to a fraction of a shared canvas —
# exactly where a subtle case (a bracket with a component printed on the
# box, a cable connector needing to be read) gets missed.
#
# Kept deliberately conservative: too large a batch risks the model losing
# track of which numbered image maps to which listing. No Ollama tier here
# — vision + structured output together is a much higher bar than most
# locally-runnable models reliably clear; this tier stays cloud-only.
VERIFICATION_BATCH_SIZE = 10

_VERIFY_TOOL_SCHEMA = {
    "name": "submit_category_verification",
    "description": "Report which numbered listings are NOT genuinely a real, standalone example of their claimed category.",
    "input_schema": {
        "type": "object",
        "properties": {
            "not_matching": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "description": "The numbered index of the listing that does not match its claimed category."},
                        "reason": {"type": "string", "description": "One short phrase for what the photo/title actually show instead."},
                    },
                    "required": ["index", "reason"],
                },
                "description": "Every listing whose photo and/or title show it is NOT a genuine standalone example of its claimed category — e.g. an accessory, mounting bracket, cable, case, empty box, or a bundle listing where the claimed category is only part of what's pictured. Empty array if every listing genuinely matches.",
            },
        },
        "required": ["not_matching"],
    },
}

_VERIFY_SYSTEM_PROMPT = """You are a product-category verification assistant for a PC component deal-screening tool.

You will be shown a numbered list of listings, each with its title, claimed category, and photo.

Your ONLY job: for each listing, decide whether the photo and title genuinely show a real, standalone
example of the claimed category — not an accessory, mounting bracket, cable, case, empty box, decal, or
a bundle where the claimed category is only one part of what's pictured.

You MUST NOT:
- State, estimate, or imply any price or value.
- Flag a listing just because the photo is low quality, at an odd angle, or the item is used or damaged —
  condition and photo quality are not your concern, only whether it is genuinely the claimed product type.
- Invent details not visible in the photo or stated in the title.

Call submit_category_verification with the numbered indices of every listing that does NOT genuinely match
its claimed category. Leave the array empty if all of them do. Do not respond with plain text."""


@dataclass
class VerificationFailure:
    listing_id: str
    reason: str


async def _fetch_image(client: httpx.AsyncClient, url: str) -> tuple[bytes, str] | None:
    try:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
    except Exception as exc:
        log.warning("gem_radar.claude_screening.image_fetch_failed", url=url, error=str(exc))
        return None
    media_type = resp.headers.get("content-type", "image/jpeg").split(";")[0]
    if not media_type.startswith("image/"):
        media_type = "image/jpeg"
    return resp.content, media_type


def _chunks(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _parse_verify_result(data: dict, index_to_listing_id: dict[int, str]) -> list[VerificationFailure]:
    try:
        not_matching = data.get("not_matching") or []
        failures = []
        for item in not_matching:
            listing_id = index_to_listing_id.get(int(item["index"]))
            if listing_id is None:
                continue
            failures.append(VerificationFailure(listing_id=listing_id, reason=str(item.get("reason") or "")))
        return failures
    except (TypeError, ValueError, KeyError) as exc:
        log.warning("gem_radar.claude_screening.verify_malformed_output", error=str(exc))
        return []


async def _fetch_batch_images(
    candidates: list[tuple[str, str, str, str]],
) -> tuple[list[tuple[str, str, bytes, str]], dict[int, str]]:
    """Returns (numbered [(listing_id, title, image_bytes, media_type)], index_to_listing_id)."""
    async with httpx.AsyncClient() as http_client:
        fetched = await asyncio.gather(*[_fetch_image(http_client, url) for *_rest, url in candidates])

    numbered: list[tuple[str, str, bytes, str]] = []
    index_to_listing_id: dict[int, str] = {}
    n = 0
    for (listing_id, title, category, _url), image in zip(candidates, fetched):
        if image is None:
            continue
        n += 1
        index_to_listing_id[n] = listing_id
        image_bytes, media_type = image
        numbered.append((title, category, image_bytes, media_type))
    return numbered, index_to_listing_id


async def _verify_one_batch(
    settings: Settings, candidates: list[tuple[str, str, str, str]], max_retries: int
) -> list[VerificationFailure]:
    """Verify a batch through the centralized vision-capable model chain."""
    numbered, index_to_listing_id = await _fetch_batch_images(candidates)
    if not numbered:
        return []
    text_parts = []
    images = []
    for n, (title, category, image_bytes, media_type) in enumerate(numbered, start=1):
        text_parts.append(f'Listing {n}: "{title}" — claimed category: {category}')
        images.append((image_bytes, media_type))
    try:
        selected = await model_selection_service.complete(
            task="Gem Radar photo category verification",
            messages=[{"role": "user", "content": "\n".join(text_parts)}],
            system_prompt=_VERIFY_SYSTEM_PROMPT, max_tokens=1024, timeout=180,
            tools=[_VERIFY_TOOL_SCHEMA], require_vision=True, require_tools=True,
            images=images,
            tool_choice={"type": "function", "function": {"name": "submit_category_verification"}},
        )
        if selected.tool_calls:
            data = selected.tool_calls[0].get("function", {}).get("arguments", {})
            if isinstance(data, str):
                data = json.loads(data)
        else:
            data = json.loads(selected.text)
        return _parse_verify_result(data, index_to_listing_id)
    except Exception as exc:
        log.warning("gem_radar.claude_screening.verify_model_selection_failed", error=str(exc))
        return []


async def verify_categories_batch(
    candidates: list[tuple[str, str, str, str]], max_retries: int = 1
) -> list[VerificationFailure]:
    """Batched photo+title category check for a set of candidates, each a
    (listing_id, title, category, image_url) tuple. Split into batches of
    VERIFICATION_BATCH_SIZE and run concurrently — one vision request per
    batch instead of per listing. Uses OpenRouter only (Anthropic removed,
    no Ollama tier for vision).

    Returns only the listings flagged as NOT matching their claimed
    category — an empty list if no provider is configured or every attempt
    fails schema validation, never a fabricated flag. Callers must not treat
    an empty result as proof every candidate is genuine, only as "nothing
    flagged".
    """
    settings = get_settings()
    if not settings.openrouter_api_key or not candidates:
        return []

    batches = _chunks(candidates, VERIFICATION_BATCH_SIZE)
    results = await asyncio.gather(
        *[_verify_one_batch(settings, batch, max_retries) for batch in batches]
    )
    return [failure for batch_failures in results for failure in batch_failures]
