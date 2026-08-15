"""AI-assisted structured spec extraction for motherboards.

Provider order follows app/services/ai_service.py's established convention,
NOT claude_evaluator.py's (which puts paid Anthropic first) — local Ollama
first (free, no rate limits, this app's actual default), then OpenRouter's
free tier, then Anthropic only as a last resort. This is a low-stakes
extraction task (one motherboard model's public spec sheet), not the kind of
high-stakes reasoning that would justify skipping straight to a paid model.

Every row this produces is saved with reviewed=False — see MotherboardSpec's
docstring for why an unreviewed AI guess must never drive a hard
incompatibility verdict on its own.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are a hardware reference database assistant. Given a \
motherboard's model name (from a marketplace listing title, which may include \
extra noise like condition or seller boilerplate), identify the exact \
motherboard model and return its known technical specifications.

If you do not recognise the exact model with reasonable confidence, set \
"recognised" to false and leave the spec fields null — do not guess or \
fabricate values you're not confident about. This data feeds a PC-compatibility \
checker; a wrong socket or RAM type is worse than an admitted "unknown".

Respond with ONLY valid JSON — no explanation, no markdown, no extra text:
{
  "recognised": true,
  "canonical_model": "ASUS ROG STRIX B650-A GAMING WIFI",
  "brand": "ASUS",
  "socket": "am5",
  "chipset": "B650",
  "ram_type": "ddr5",
  "ram_slots": 4,
  "max_ram_gb": 128,
  "pcie_x16_slots": 2,
  "m2_slots": 3,
  "sata_ports": 4,
  "form_factor": "atx",
  "wifi": true,
  "confidence": 0.9,
  "reasoning": "Well-known current-gen AMD board, specs match ASUS's published datasheet."
}"""


@dataclass
class MotherboardSpecAIResult:
    recognised: bool
    canonical_model: str | None
    brand: str | None
    socket: str | None
    chipset: str | None
    ram_type: str | None
    ram_slots: int | None
    max_ram_gb: int | None
    pcie_x16_slots: int | None
    m2_slots: int | None
    sata_ports: int | None
    form_factor: str | None
    wifi: bool | None
    confidence: float
    reasoning: str
    raw: dict


async def _try_ollama(settings, user_content: str) -> str | None:
    if not settings.ollama_base_url:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content")
    except Exception as exc:
        log.warning("motherboard_spec_ai.ollama_failed", error=str(exc), exc_type=type(exc).__name__)
        return None


async def _try_openrouter(settings, user_content: str) -> str | None:
    if not settings.openrouter_api_key:
        return None
    try:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "HTTP-Referer": settings.frontend_url,
                    "X-Title": "FlipFlop Motherboard Spec Backfill",
                },
                json={
                    "model": settings.openrouter_primary_model or "meta-llama/llama-3.1-8b-instruct",
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "max_tokens": 400,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except Exception as exc:
        log.warning("motherboard_spec_ai.openrouter_failed", error=str(exc))
        return None


async def _try_anthropic(settings, user_content: str) -> str | None:
    if not settings.anthropic_api_key:
        return None
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model="claude-opus-4-8",
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        return resp.content[0].text if resp.content else None
    except Exception as exc:
        log.warning("motherboard_spec_ai.anthropic_failed", error=str(exc))
        return None


async def extract_motherboard_spec(title: str) -> MotherboardSpecAIResult | None:
    settings = get_settings()
    user_content = f"Motherboard listing title: {title}"

    # Local first (free, this app's actual default per ai_service.py) → free
    # OpenRouter tier → paid Anthropic only as a last resort.
    raw_text = await _try_ollama(settings, user_content)
    if not raw_text:
        raw_text = await _try_openrouter(settings, user_content)
    if not raw_text:
        raw_text = await _try_anthropic(settings, user_content)

    if not raw_text:
        return None

    match = re.search(r"\{[\s\S]*\}", raw_text)
    if not match:
        log.warning("motherboard_spec_ai.no_json", raw=raw_text[:200])
        return None

    try:
        d = json.loads(match.group())
    except json.JSONDecodeError as exc:
        log.warning("motherboard_spec_ai.json_error", error=str(exc), raw=raw_text[:200])
        return None

    return MotherboardSpecAIResult(
        recognised=bool(d.get("recognised")),
        canonical_model=d.get("canonical_model"),
        brand=d.get("brand"),
        socket=(d.get("socket") or None) and str(d.get("socket")).lower(),
        chipset=d.get("chipset"),
        ram_type=(d.get("ram_type") or None) and str(d.get("ram_type")).lower(),
        ram_slots=d.get("ram_slots"),
        max_ram_gb=d.get("max_ram_gb"),
        pcie_x16_slots=d.get("pcie_x16_slots"),
        m2_slots=d.get("m2_slots"),
        sata_ports=d.get("sata_ports"),
        form_factor=(d.get("form_factor") or None) and str(d.get("form_factor")).lower(),
        wifi=d.get("wifi"),
        confidence=float(d.get("confidence") or 0.0),
        reasoning=str(d.get("reasoning") or ""),
        raw=d,
    )
