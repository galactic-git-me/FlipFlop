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


async def _screen_via_anthropic(
    settings: Settings, user_prompt: str, max_retries: int
) -> ClaudeAssistResult | None:
    if not settings.anthropic_api_key:
        return None

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    for attempt in range(max_retries + 1):
        try:
            response = await client.messages.create(
                model="claude-opus-4-8",
                max_tokens=512,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[_ASSESS_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "submit_identity_and_risk_assessment"},
            )
        except Exception as exc:
            log.warning("gem_radar.claude_screening.anthropic_failed", attempt=attempt, error=str(exc))
            continue

        tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use_block is None:
            log.warning("gem_radar.claude_screening.anthropic_no_tool_use_block", attempt=attempt)
            continue

        result = _parse_assist_result(tool_use_block.input)
        if result is not None:
            return result

    return None


async def _openrouter_tool_call(
    settings: Settings,
    system_prompt: str,
    user_content,
    tool_schema: dict,
    max_tokens: int,
    max_retries: int,
) -> dict | None:
    """OpenAI-compatible tool-calling request to OpenRouter. user_content can
    be a plain string (text-only) or a list of OpenAI-format content blocks
    (text + image_url). Returns the parsed tool-call arguments dict, or None
    — same never-fabricate contract as the Anthropic tier."""
    if not settings.openrouter_api_key:
        return None

    model = settings.openrouter_primary_model or "meta-llama/llama-3.1-8b-instruct"
    tool_name = tool_schema["name"]
    openai_tool = {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": tool_schema["description"],
            "parameters": tool_schema["input_schema"],
        },
    }

    for attempt in range(max_retries + 1):
        try:
            wait = (2**attempt) * 5
            if attempt > 0:
                await asyncio.sleep(wait)
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "HTTP-Referer": "http://localhost:3000",
                        "X-Title": "FlipFlop Gem Radar",
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_content},
                        ],
                        "tools": [openai_tool],
                        "tool_choice": {"type": "function", "function": {"name": tool_name}},
                        "max_tokens": max_tokens,
                    },
                )
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get("Retry-After", wait))
                    log.warning("gem_radar.claude_screening.openrouter_rate_limited", attempt=attempt)
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                data = resp.json()
                tool_calls = data["choices"][0]["message"].get("tool_calls") or []
                if not tool_calls:
                    log.warning("gem_radar.claude_screening.openrouter_no_tool_call", attempt=attempt)
                    continue
                return json.loads(tool_calls[0]["function"]["arguments"])
        except Exception as exc:
            log.warning("gem_radar.claude_screening.openrouter_failed", attempt=attempt, error=str(exc))
            continue

    return None


async def _screen_via_openrouter(
    settings: Settings, user_prompt: str, max_retries: int
) -> ClaudeAssistResult | None:
    data = await _openrouter_tool_call(
        settings, _SYSTEM_PROMPT, user_prompt, _ASSESS_TOOL_SCHEMA, max_tokens=512, max_retries=max_retries
    )
    return _parse_assist_result(data) if data is not None else None


async def _screen_via_ollama(settings: Settings, user_prompt: str) -> ClaudeAssistResult | None:
    """Local primary screening — fast GPU-accelerated inference, no rate limits.
    No forced tool schema (Qwen models don't support tool-calling as reliably
    as OpenRouter), so this asks for JSON via Ollama's format="json" mode
    instead and parses leniently. Text-only screening still goes through
    _parse_assist_result's validation, so malformed JSON fails safe (returns None)."""
    if not settings.ollama_base_url:
        return None
    try:
        # Separate connect timeout, not one blanket 180s: a dead/unreachable
        # host (DNS failure, VPN down) should fail in ~5s, not burn the full
        # budget meant for slow local inference once actually connected —
        # otherwise every listing needing this fallback wastes nearly its
        # whole per-listing timeout on a connection that was never going to
        # succeed, starving the rest of the batch for no benefit.
        timeout = httpx.Timeout(connect=5.0, read=15.0, write=10.0, pool=5.0)
        async with _ollama_semaphore, httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": _SYSTEM_PROMPT
                            + "\n\nRespond with ONLY a single JSON object with these exact keys: "
                            "canonical_name, canonical_model_id, identity_confidence, release_year, is_bundle, "
                            "bundle_components, additional_risk_notes, reasoning_summary.",
                        },
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": "json",
                    "stream": False,
                },
            )
            resp.raise_for_status()
            content = resp.json().get("message", {}).get("content")
            if not content:
                return None
            return _parse_assist_result(json.loads(content))
    except Exception as exc:
        log.warning("gem_radar.claude_screening.ollama_failed", error=str(exc))
        return None


async def screen_with_claude(
    listing: ExtractedListing, identity: Identity, max_retries: int = 2
) -> ClaudeAssistResult | None:
    """Returns None (not a fabricated result) if every configured provider
    is unavailable or every attempt fails schema validation — callers must
    fall back to the deterministic-only assessment, never synthesize an
    LLM opinion.

    Provider priority: Ollama (local, fast, GPU) -> OpenRouter (cloud, fallback)
    """
    settings = get_settings()
    if not (settings.openrouter_api_key or settings.ollama_base_url):
        log.info("gem_radar.claude_screening.no_provider_configured")
        return None

    user_prompt = _build_user_prompt(listing, identity)

    # Try local Ollama first (fast, GPU-accelerated, no rate limits)
    result = await _screen_via_ollama(settings, user_prompt)
    if result is not None:
        return result

    # Fall back to OpenRouter (cloud, when local is unavailable)
    return await _screen_via_openrouter(settings, user_prompt, max_retries)


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


async def _verify_batch_via_anthropic(
    client, numbered: list, index_to_listing_id: dict[int, str], max_retries: int
) -> list[VerificationFailure]:
    content: list[dict] = []
    for n, (title, category, image_bytes, media_type) in enumerate(numbered, start=1):
        content.append({"type": "text", "text": f'Listing {n}: "{title}" — claimed category: {category}'})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": base64.standard_b64encode(image_bytes).decode("ascii"),
                },
            }
        )
    if not content:
        return []

    for attempt in range(max_retries + 1):
        try:
            response = await client.messages.create(
                model="claude-opus-4-8",
                max_tokens=1024,
                system=_VERIFY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
                tools=[_VERIFY_TOOL_SCHEMA],
                tool_choice={"type": "tool", "name": "submit_category_verification"},
            )
        except Exception as exc:
            log.warning("gem_radar.claude_screening.verify_request_failed", attempt=attempt, error=str(exc))
            continue

        tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use_block is None:
            log.warning("gem_radar.claude_screening.verify_no_tool_use_block", attempt=attempt)
            continue

        failures = _parse_verify_result(tool_use_block.input, index_to_listing_id)
        if failures or tool_use_block.input.get("not_matching") == []:
            return failures

    return []


async def _verify_batch_via_openrouter(
    settings: Settings, numbered: list, index_to_listing_id: dict[int, str], max_retries: int
) -> list[VerificationFailure]:
    content: list[dict] = []
    for n, (title, category, image_bytes, media_type) in enumerate(numbered, start=1):
        content.append({"type": "text", "text": f'Listing {n}: "{title}" — claimed category: {category}'})
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        content.append({"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}})
    if not content:
        return []

    data = await _openrouter_tool_call(
        settings, _VERIFY_SYSTEM_PROMPT, content, _VERIFY_TOOL_SCHEMA, max_tokens=1024, max_retries=max_retries
    )
    if data is None:
        return []
    return _parse_verify_result(data, index_to_listing_id)


async def _verify_one_batch(
    settings: Settings, candidates: list[tuple[str, str, str, str]], max_retries: int
) -> list[VerificationFailure]:
    """candidates: list of (listing_id, title, category, image_url).

    Only uses OpenRouter (Anthropic removed). No local tier for vision."""
    numbered, index_to_listing_id = await _fetch_batch_images(candidates)
    if not numbered:
        return []

    return await _verify_batch_via_openrouter(settings, numbered, index_to_listing_id, max_retries)


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
