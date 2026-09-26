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
import re
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

from app.config import get_settings
from app.services.model_selection_service import model_selection_service
from app.services.case_product_key import case_product_key

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

# Common chassis families are much easier to identify deterministically than
# through a free-form model response.  This also handles used/empty cases and
# case bundles, where the title often contains plenty of useful identity but
# little prose the LLM can rely on.
_CASE_FAMILY_PATTERNS = (
    ("corsair", r"(?:3500x|4000d|5000d|6500d|7000d|2500x|2500d|frame\s+(?:4000d|4500x)|4500x)"),
    ("nzxt", r"(?:h[1-9]\d?|f[1-9]\d?|h[2-9]\d{2}|f[2-9]\d{2})"),
    ("fractal-design", r"(?:define\s+[rst]\d+|focus\s+g|meshify\s+[a-z]\d*|north(?:\s+xl)?)"),
    ("cooler-master", r"(?:nr\d{3,4}p?(?:\s+max)?|masterbox\s+[a-z0-9-]+)"),
    ("phanteks", r"(?:evolv(?:\s+x2?)?|nv\d{2,3}|g\d{2,3})"),
    ("montech", r"(?:air\s*\d{2,3}|sky\s*(?:two|one)|hs\d{2,3})"),
    ("kolink", r"(?:inspire\s+[a-z]\d+|observatory\s+[a-z]\d+)"),
    ("lian-li", r"(?:o\d{2,3}|lancool\s+[a-z0-9-]+|dynamic\s+[a-z0-9-]+)"),
    ("antec", r"(?:nx\d{3}|p\d{3}|df\d{2,3})"),
    ("thermaltake", r"(?:core\s+[a-z0-9-]+|versa\s+[a-z0-9-]+)"),
)


def extract_case_identity(title: str) -> tuple[str, str] | None:
    """Return a conservative (brand, model) for recognisable PC cases."""
    lowered = title.lower()
    if not re.search(r"\b(?:pc|computer)\s+(?:case|chassis)\b|\bchassis\b", lowered):
        return None
    for brand, model_pattern in _CASE_FAMILY_PATTERNS:
        brand_pattern = re.escape(brand).replace(r"\-", r"\s+")
        match = re.search(rf"\b{brand_pattern}\b", lowered)
        if match:
            model = re.search(model_pattern, lowered[match.end():])
            if model:
                return brand, _slug(model.group(0))
    return None


def _is_placeholder_echo(value: str) -> bool:
    lowered = value.lower()
    return any(marker in lowered for marker in _PLACEHOLDER_ECHO_MARKERS)


def _safe_title(title: str, limit: int = 50) -> str:
    """Return an ASCII-safe representation for Windows console logging."""
    return title[:limit].encode("ascii", errors="backslashreplace").decode("ascii")


def _slug(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-")


def canonical_variant_model(category: str, model: str, title: str) -> str:
    """Add value-defining variants which a product-line name omits."""
    result = _slug(model)
    lowered = title.lower()
    if category in {"ssd", "ram"}:
        capacities = re.findall(r"\b(\d+(?:\.\d+)?)\s*(tb|gb)\b", lowered)
        if len(set(capacities)) == 1:
            value, unit = capacities[0]
            token = f"{value}{unit}"
            if token not in result:
                result = f"{result}-{token}"
    elif category == "gpu":
        vram = re.search(r"\b(\d{1,2})\s*gb\s*(?:gddr\d\w*|vram|graphics)?\b", lowered)
        if vram and f"{vram.group(1)}gb" not in result:
            result = f"{result}-{vram.group(1)}gb"
    elif category == "cooler":
        radiator = re.search(r"\b(120|140|240|280|360|420)\s*mm\b", lowered)
        if radiator and f"{radiator.group(1)}mm" not in result:
            result = f"{result}-{radiator.group(1)}mm"
    return result

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
    case_identity = extract_case_identity(title)
    if case_identity and (category is None or category == "case"):
        brand, model = case_identity
        return ExtractedProductData(
            category="case",
            brand=brand,
            model=model,
            specs={},
            confidence=0.92,
            cpk=case_product_key(title),
        )

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

CASE GUIDANCE:
   - A case-only or empty-chassis listing is still a valid case product
   - A case bundled with a PSU or fans is still a valid case product
   - Use the chassis brand/model as the identity; do not reject it because
     other included items are mentioned

EXAMPLES:
Input: "AMD Ryzen 7 3800X 8-Core 16-Thread Socket AM4 Processor"
Output: {{"category":"cpu","brand":"amd","model":"ryzen-7-3800x","specs":{{"cores":8,"threads":16,"socket":"am4"}},"confidence":0.95,"extraction_notes":"clear specs"}}

Input: "NVIDIA RTX 4080 16GB GDDR6X Gaming GPU"
Output: {{"category":"gpu","brand":"nvidia","model":"rtx-4080","specs":{{"vram_gb":16,"memory_type":"gddr6x"}},"confidence":0.9,"extraction_notes":"model inferred from title"}}

Input: "Mystery Box - PC Parts"
Output: {{"category":null,"brand":null,"model":null,"specs":{{}},"confidence":0.0,"extraction_notes":"no product data"}}
"""

    # Keep extractions from flooding the local model gateway during scans.
    try:
        async with _CPK_EXTRACTOR_SEMAPHORE:
            selected = await model_selection_service.complete(
                task="Gem Radar canonical product extraction",
                messages=[{"role": "user", "content": prompt}],
                system_prompt="Return only valid JSON. Do not use markdown or explanations.",
                max_tokens=256, timeout=45, json_mode=True,
            )
        output = selected.text.strip()
        try:
            data = json.loads(output)
        except json.JSONDecodeError:
            import re
            match = re.search(r'\{.*\}', output, re.DOTALL)
            if not match:
                log.warning("cpk_extractor.json_parse_failed", output=output[:100])
                return None
            data = json.loads(match.group())

        # Identity is upstream of every market cohort. Only high-confidence
        # model extractions may receive a canonical product key.
        if data.get("confidence", 0) < 0.7:
            log.debug("cpk_extractor.low_confidence", title=_safe_title(title), confidence=data.get("confidence"))
            return None

        category, brand, model = data.get("category"), data.get("brand"), data.get("model")
        if not (category and brand and model):
            return None

        if _is_placeholder_echo(brand) or _is_placeholder_echo(model):
            log.warning("cpk_extractor.placeholder_echo", title=_safe_title(title), category=category)
            return None

        if category not in _VALID_CATEGORIES:
            log.debug("cpk_extractor.invalid_category", title=_safe_title(title), category=category)
            return None

        data["brand"] = _slug(str(data["brand"]))
        data["model"] = canonical_variant_model(data["category"], str(data["model"]), title)
        if not data["brand"] or not data["model"]:
            return None
        cpk_input = f"{data['category']}|{data['brand']}|{data['model']}"
        cpk = hashlib.sha256(cpk_input.encode()).hexdigest()[:16]

        return ExtractedProductData(
            category=data["category"], brand=data["brand"], model=data["model"],
            specs=data.get("specs", {}), confidence=data.get("confidence", 0), cpk=cpk,
        )
    except Exception as exc:
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

