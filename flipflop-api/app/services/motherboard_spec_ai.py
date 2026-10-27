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


def title_verified_motherboard_facts(title: str) -> dict:
    """Extract only compatibility fields literally stated in a listing title.

    LLM output can suggest a model identity, but it cannot turn remembered or
    inferred specifications into source evidence. Unstated fields stay absent.
    """
    text = re.sub(r"[^a-z0-9]+", " ", (title or "").casefold())
    facts = {}
    socket = re.search(r"\b(am4|am5|lga\s?\d{4})\b", text)
    if socket:
        facts['socket'] = re.sub(r"\s+", "", socket.group(1))
    memory = re.search(r"\bddr\s?([45])\b", text)
    if memory:
        facts['ram_type'] = f"ddr{memory.group(1)}"
    chipset = re.search(r"\b([abxzh]\d{3,4}e?)[a-z]?\b", text)
    if chipset:
        facts['chipset'] = chipset.group(1)
    if re.search(r"\b(micro\s?atx|m\s?atx|matx)\b", text):
        facts['form_factor'] = 'matx'
    elif re.search(r"\batx\b", text):
        facts['form_factor'] = 'atx'
    elif re.search(r"\bitx\b", text):
        facts['form_factor'] = 'itx'
    slot_count = re.search(r"\b(2|4|6|8)\s*(?:x\s*)?(?:dimm|memory|ram)\s*slots?\b", text)
    if slot_count:
        facts['ram_slots'] = int(slot_count.group(1))
    maximum = re.search(r"\b(?:max(?:imum)?\s*)?(\d{2,3})\s*gb\s*(?:max(?:imum)?\s*)?(?:memory|ram)\b", text)
    if maximum:
        facts['max_ram_gb'] = int(maximum.group(1))
    pcie_count = re.search(r"\b(\d+)\s*x\s*(?:pcie|pci express)(?:\s*\d+){0,2}\s*x\s*16\b", text)
    if pcie_count:
        facts['pcie_x16_slots'] = int(pcie_count.group(1))
    m2_count = re.search(r"\b(\d+)\s*x\s*m\s*2\b", text)
    if m2_count:
        facts['m2_slots'] = int(m2_count.group(1))
    sata_count = re.search(r"\b(\d+)\s*x\s*sata\b", text)
    if sata_count:
        facts['sata_ports'] = int(sata_count.group(1))
    if re.search(r"\bwi\s?fi\d*\b", text):
        facts['wifi'] = True
    return facts


async def extract_motherboard_spec(title: str, *, free_only: bool = True) -> MotherboardSpecAIResult | None:
    user_content = f"Motherboard listing title: {title}"
    try:
        result = await model_selection_service.complete(
            task="Motherboard specification extraction",
            messages=[{"role": "user", "content": user_content}],
            system_prompt=_SYSTEM_PROMPT, max_tokens=400, free_only=free_only,
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
        reasoning=str(d.get("reasoning") or "")[:500],
        raw=d,
    )
