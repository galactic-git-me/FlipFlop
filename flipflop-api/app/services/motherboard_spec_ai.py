"""AI-assisted structured spec extraction for motherboards.

Provider order follows the environment-configured model selection hierarchy:
local Ollama, OpenRouter free tier, then the cheapest paid OpenRouter model.
This is a low-stakes extraction task (one motherboard model's public spec
sheet).

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
from app.services.model_selection_service import model_selection_service

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


async def extract_motherboard_spec(title: str) -> MotherboardSpecAIResult | None:
    user_content = f"Motherboard listing title: {title}"
    try:
        result = await model_selection_service.complete(
            task="Motherboard specification extraction",
            messages=[{"role": "user", "content": user_content}],
            system_prompt=_SYSTEM_PROMPT, max_tokens=400,
        )
        raw_text = result.text
    except Exception as exc:
        log.warning("motherboard_spec_ai.all_models_failed", error=str(exc))
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
