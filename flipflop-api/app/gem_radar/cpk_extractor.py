"""
Canonical Product Key (CPK) extraction via local LLM.

Extracts structured product data from marketplace listings using Qwen2:7b,
creates a deterministic product consolidation key, and stores metadata for
cross-vendor price aggregation.

Usage:
  cpk = await extract_cpk(title="AMD Ryzen 7 3800X", category="cpu", condition="used")
"""
from __future__ import annotations

import asyncio
import json
import hashlib
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

# Limit concurrent Ollama requests to 4 (optimal for Qwen2:7b on GPU)
# Tested 5 but hit VRAM exhaustion — 4 is the sweet spot
_CPK_EXTRACTOR_SEMAPHORE = asyncio.Semaphore(4)

# The only categories the prompt's own schema comment offers the model — a
# multi-category answer like "cpu|gpu" (seen on full-PC-bundle listings) or
# any other value means the model is guessing/hedging rather than naming one
# real standalone part, and must not be accepted as a CPK-hash input.
_VALID_CATEGORIES = {"cpu", "gpu", "motherboard", "ram", "ssd", "psu", "cooler", "case", "fan"}

# Substrings that only ever appear in the PROMPT's own field-description text
# ("brand": "lowercase brand name", "model": "normalized-model-id
# (lowercase, dash-separated, no spaces)") — never in a real extracted value.
# Confirmed via production data: Qwen2:7b periodically echoes these template
# strings back verbatim instead of filling them in, and since validation
# previously only checked "is this non-empty" (not "is this real"), every
# listing that triggered it got hashed into the exact same CPK as every
# *other* listing that triggered it for that category — a £5 accessory,
# a £600 GPU, and a full gaming PC all landing in one "market price" bucket
# together purely because the model gave up on the same three listings'
# worth of prompt text. See gem_radar audit 2026-08-14: one such bucket
# (category="unknown") collapsed 703 unrelated listings into a single CPK.
_PLACEHOLDER_ECHO_MARKERS = (
    "brand name",
    "model-id",
    "dash-separated",
    "no spaces",
)


def _is_placeholder_echo(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_ECHO_MARKERS)


def _safe_title(title: str, limit: int = 50) -> str:
    """Encode title to be safe for logging (handles non-ASCII characters)."""
    return title[:limit].encode('utf-8', errors='replace').decode('utf-8', errors='replace')

@dataclass
class ExtractedProductData:
    """Structured product info extracted from title."""
    category: str  # cpu, gpu, motherboard, ram, ssd, psu, cooler, case, fan
    brand: str  # amd, intel, nvidia, corsair, etc.
    model: str  # normalized model identifier (e.g., "ryzen-7-3800x")
    specs: dict  # brand/model-specific: {"cores": 8, "threads": 16, "socket": "am4"}
    confidence: float  # 0.0-1.0, quality of extraction
    cpk: str  # Canonical Product Key hash

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "brand": self.brand,
            "model": self.model,
            "specs": self.specs,
            "confidence": self.confidence,
            "cpk": self.cpk,
        }


async def extract_cpk(
    title: str,
    category: Optional[str] = None,
    condition: Optional[str] = None,
) -> ExtractedProductData | None:
    """
    Extract structured product data from a listing title using Qwen2:7b.

    Args:
        title: Listing title (e.g., "AMD Ryzen 7 3800X 8-Core Processor")
        category: Detected category (cpu, gpu, etc.) — helps guide extraction
        condition: API condition (new, used, unknown) — not parsed from title

    Returns:
        ExtractedProductData with CPK, or None if extraction fails/confidence too low
    """
    prompt = f"""You are a PC hardware product data extractor. Extract structured info from this listing title.

TITLE: {title}
DETECTED_CATEGORY: {category or "unknown"}
CONDITION: {condition or "unknown"}

Extract and return ONLY valid JSON (no markdown, no explanation):
{{
  "category": "cpu|gpu|motherboard|ram|ssd|psu|cooler|case|fan",
  "brand": "lowercase brand name",
  "model": "normalized-model-id (lowercase, dash-separated, no spaces)",
  "specs": {{"key": "value", ...}},
  "confidence": 0.0 to 1.0,
  "extraction_notes": "why this confidence; any ambiguities"
}}

RULES:
1. category: Use DETECTED_CATEGORY if provided and correct; otherwise infer from title
2. brand: Normalize to lowercase (AMD→amd, Intel→intel, NVIDIA→nvidia)
3. model: Normalize spaces/special chars to dashes (Ryzen 7 3800X → ryzen-7-3800x)
4. specs: Extract relevant specs by category:
   - CPU: cores, threads, socket, tdp, clock_mhz (if visible)
   - GPU: vram_gb, memory_type, cuda_cores (if inferrable)
   - RAM: capacity_gb, speed_mhz, type (ddr4/ddr5), ecc (yes/no)
   - SSD: capacity_gb, form_factor (m.2/2.5), interface (nvme/sata), speed_mbps
5. confidence: 1.0=perfect extraction, 0.5=partial/ambiguous, 0.0=unrecognizable
6. Return empty/unmatched specs as null, not strings

EXAMPLES:
Input: "AMD Ryzen 7 3800X 8-Core 16-Thread Socket AM4 Processor"
Output: {{"category":"cpu","brand":"amd","model":"ryzen-7-3800x","specs":{{"cores":8,"threads":16,"socket":"am4"}},"confidence":0.95,"extraction_notes":"clear specs"}}

Input: "NVIDIA RTX 4080 16GB GDDR6X Gaming GPU"
Output: {{"category":"gpu","brand":"nvidia","model":"rtx-4080","specs":{{"vram_gb":16,"memory_type":"gddr6x"}},"confidence":0.9,"extraction_notes":"model inferred from title"}}

Input: "Mystery Box - PC Parts"
Output: {{"category":null,"brand":null,"model":null,"specs":{{}},"confidence":0.0,"extraction_notes":"no product data"}}
"""

    # Retry up to 4 times for transient errors, backing off exponentially
    # (1s, 2s, 4s) rather than a flat 1s -- a flat delay gives up in ~2s
    # total, too short to survive Ollama being briefly unreachable (e.g. a
    # WSL/Docker network hiccup), which is exactly the failure mode that
    # was permanently stranding listings without a CPK for the rest of
    # that run (see cpk_extractor.exception in the logs).
    settings = get_settings()
    max_attempts = 4

    for attempt in range(max_attempts):
        try:
            async with _CPK_EXTRACTOR_SEMAPHORE:
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        f"{settings.ollama_base_url}/api/generate",
                        json={
                            "model": "qwen2.5:7b",
                            "prompt": prompt,
                            "stream": False,
                            "temperature": 0.1,  # Low temp for deterministic output
                        },
                    )

                if resp.status_code == 500:
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
                        continue
                    else:
                        log.warning("cpk_extractor.ollama_error", status=resp.status_code, attempt=attempt)
                        return None
                elif resp.status_code != 200:
                    log.warning("cpk_extractor.ollama_error", status=resp.status_code)
                    return None

                # Success, process response
                result = resp.json()
                output = result.get("response", "").strip()

                # Extract JSON from response
                try:
                    data = json.loads(output)
                except json.JSONDecodeError:
                    # Try to find JSON in output (model might add text before/after)
                    import re
                    match = re.search(r'\{.*\}', output, re.DOTALL)
                    if not match:
                        safe_output = output[:100].encode('utf-8', errors='replace').decode('utf-8', errors='replace')
                        log.warning("cpk_extractor.json_parse_failed", output=safe_output)
                        return None
                    data = json.loads(match.group())

                # Skip if confidence too low (ambiguous/unrecognizable)
                # Threshold lowered to 0.2 to accept more partial/ambiguous extractions
                # Phase 2 will filter based on market-price settlement instead
                if data.get("confidence", 0) < 0.2:
                    log.debug("cpk_extractor.low_confidence", title=_safe_title(title), confidence=data.get("confidence"))
                    return None

                # Skip if no category/brand/model
                category, brand, model = data.get("category"), data.get("brand"), data.get("model")
                if not (category and brand and model):
                    return None

                # Skip if the model echoed its own prompt's field-description
                # text back as the value instead of extracting real data —
                # see _PLACEHOLDER_ECHO_MARKERS above. Accepting this as
                # valid previously meant every listing hitting this failure
                # mode for the same category collapsed into one shared,
                # nonsense CPK.
                if _is_placeholder_echo(brand) or _is_placeholder_echo(model):
                    log.warning("cpk_extractor.placeholder_echo", title=_safe_title(title), category=category)
                    return None

                # Skip multi-category answers ("cpu|gpu") — a real standalone
                # part is exactly one category; a hedge/join means the model
                # couldn't tell (typically a full-PC bundle slipping past
                # DETECTED_CATEGORY), and accepting it collapses every such
                # bundle into one shared CPK regardless of its actual parts.
                if category not in _VALID_CATEGORIES:
                    log.debug("cpk_extractor.invalid_category", title=_safe_title(title), category=category)
                    return None

                # Generate Canonical Product Key from category|brand|model ONLY.
                # `specs` is deliberately excluded from the hash input: it's a
                # free-form dict the LLM extracts per-listing from whatever
                # detail happens to appear in that seller's title, so it varies
                # listing-to-listing for the exact same physical product (one
                # seller's title mentions cores/threads/socket, another's
                # doesn't). Since this is a cryptographic hash with no fuzzy
                # matching, including specs meant two listings of the identical
                # product almost never produced the same CPK — silently
                # preventing get_market_price() from ever seeing 2+ listings
                # share a key, so market prices never settled. specs is still
                # captured in cpk_data for display/debugging, just not hashed.
                cpk_input = f"{data['category']}|{data['brand']}|{data['model']}"
                cpk = hashlib.sha256(cpk_input.encode()).hexdigest()[:16]  # 16-char hex

                return ExtractedProductData(
                    category=data["category"],
                    brand=data["brand"],
                    model=data["model"],
                    specs=data.get("specs", {}),
                    confidence=data.get("confidence", 0),
                    cpk=cpk,
                )

        except Exception as exc:
            if attempt < max_attempts - 1:
                await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s
                continue
            log.warning("cpk_extractor.exception", error=str(exc), title=_safe_title(title))
            return None


async def test_extraction():
    """Test extraction on sample listings."""
    samples = [
        ("MSI NVIDIA GeForce GT 1030 2GB GDDR5 Graphics Card GPU", "gpu", "used"),
        ("AMD Ryzen 7 3800X 8-Core 16-Thread Socket AM4 Processor", "cpu", "new"),
        ("Corsair Vengeance RGB 32GB DDR4 3200MHz RAM Kit", "ram", "new"),
        ("Samsung 970 EVO Plus 1TB M.2 NVMe SSD", "ssd", "new"),
        ("Mystery Box - PC Parts", "case", "unknown"),
    ]

    print("CPK Extraction Test Results:")
    print("=" * 100)

    for title, category, condition in samples:
        result = await extract_cpk(title, category, condition)
        print(f"\nTitle: {title[:70]}")
        if result:
            print(f"  Category: {result.category} | Brand: {result.brand} | Model: {result.model}")
            print(f"  Specs: {result.specs}")
            print(f"  CPK: {result.cpk}")
            print(f"  Confidence: {result.confidence:.2f}")
        else:
            print("  [SKIPPED] Extraction failed (low confidence or parsing error)")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_extraction())

