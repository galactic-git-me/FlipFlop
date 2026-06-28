"""
AI evaluation for parts catalogue gems.

Asks Claude whether a specific PC component is genuinely priced below
current UK eBay market value, using its knowledge of current component prices.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)

PART_EVAL_SYSTEM = """You are an expert UK PC component market analyst.
Evaluate whether a specific second-hand PC component is genuinely priced below
current eBay UK market value.

STEP 1 — REJECT immediately (return "REJECT", confidence 1.0) if the item is NOT
a genuine desktop PC component. Examples of things that must be REJECTED:
- Game discs, cartridges, or software (PS3 game, Xbox game, any game title)
- USB flash drives, pen drives, memory sticks, SD cards
- Laptop or notebook components (mobile GPUs, laptop RAM, laptop SSDs)
- Accessories, brackets, backplates, I/O shields, retention brackets
- CPU coolers listed under CPU category (they are not CPUs)
- Empty retail boxes or packaging only ("box only", "OEM box")
- Peripherals: mice, keyboards, headsets, controllers, monitors
- Want ads or requests ("NEEDED", "WANTED", "looking for")
- Price strings or gibberish that is not a product name
- Retro/legacy storage (IDE drives, PATA, floppy, ZIP drives)
- Any item clearly not a desktop GPU / CPU / RAM stick / NVMe or SATA SSD / ATX PSU / desktop motherboard / CPU cooler

STEP 2 — For genuine desktop PC components, evaluate against current UK eBay used prices:

CURRENT UK ЕБAY USED PRICE RANGES (2025/26):
- GPU: RTX 3060 12GB £120-160, RTX 3070 8GB £160-200, RTX 3080 10GB £200-260, RX 6700 XT £120-160, RTX 2070 Super £100-140, RTX 2080 Ti £160-220
- CPU: Ryzen 5 5600X £70-100, Ryzen 7 5700X £90-120, i5-12600K £100-140, i7-12700K £150-200, i5-13600K £130-170, Ryzen 9 5900X £150-200
- RAM: 16GB DDR4 kit £12-22, 32GB DDR4 kit £22-40, 16GB DDR5 kit £25-45, 32GB DDR5 kit £50-90
- SSD: 500GB NVMe £25-45, 1TB NVMe £45-75, 2TB NVMe £80-130, 500GB SATA £15-30, 1TB SATA £25-45
- PSU: 650W 80+ Bronze £30-55, 750W 80+ Gold £50-85, 850W 80+ Gold £70-110
- Motherboard: B550 ATX £50-85, X570 ATX £75-120, B650 ATX £90-150, Z690 ATX £100-160
- Cooler: budget 120mm £8-18, Hyper 212/similar £15-30, 240mm AIO £40-80

VERDICT DEFINITIONS:
- GEM: Price is 30%+ below current UK eBay used value — genuine bargain, strong buy signal
- GOOD: Price is 15-29% below current UK eBay used value — worthwhile deal
- REJECT: Price is within 15% of market, above market, item is not a genuine PC component, or you cannot confidently identify the item

Respond with ONLY valid JSON, no markdown:
{
  "verdict": "GEM",
  "market_price_estimate": 155,
  "confidence": 0.85,
  "reasoning": "RTX 3060 12GB typically sells for £130-165 used on eBay UK. At £82 this is ~47% below midpoint — strong gem."
}"""

_VALID_VERDICTS = {"GEM", "GOOD", "REJECT"}


@dataclass
class PartGemResult:
    verdict: str
    market_price_estimate: float
    confidence: float
    reasoning: str
    model_used: str


def _build_part_prompt(d: dict) -> str:
    price = d.get("cheapest_good_price") or 0
    score = d.get("gem_score") or 0
    lines = [
        "COMPONENT TO EVALUATE:",
        f"  Name:        {d.get('name', '?')}",
        f"  Category:    {d.get('category', '?')}",
        f"  Price found: £{price:.0f}",
        f"  Source:      {d.get('cheapest_good_source', '?')}",
        "",
        "RULE-BASED PRE-SCORE:",
        f"  Discount vs tier median: {score:.1f}%",
        f"  Classification:          {d.get('gem_classification', 'none')}",
        "",
        "Is this component genuinely priced below current UK eBay market value?",
    ]
    return "\n".join(lines)


async def evaluate_part(part_data: dict) -> PartGemResult | None:
    """Send part data to the best available AI and return a verdict. Returns None if all backends fail."""
    from app.config import get_settings
    _s = get_settings()

    prompt = _build_part_prompt(part_data)
    messages = [{"role": "user", "content": prompt}]
    raw: str | None = None
    model_used = "none"

    if not raw and _s.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=_s.anthropic_api_key)
            resp = await client.messages.create(
                model="claude-opus-4-8",
                max_tokens=256,
                system=PART_EVAL_SYSTEM,
                messages=messages,
            )
            raw = resp.content[0].text if resp.content else None
            model_used = "claude-opus-4-8"
        except Exception as exc:
            log.warning("part_gem_evaluator.anthropic_failed", error=str(exc))

    if not raw and _s.openrouter_api_key:
        import httpx
        for attempt in range(3):
            try:
                if attempt > 0:
                    await asyncio.sleep(5 * attempt)
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {_s.openrouter_api_key}",
                            "HTTP-Referer": "http://localhost:3000",
                            "X-Title": "PC Flipper Parts Gem Evaluator",
                        },
                        json={
                            "model": _s.openrouter_primary_model or "meta-llama/llama-3.1-8b-instruct",
                            "messages": [
                                {"role": "system", "content": PART_EVAL_SYSTEM},
                                {"role": "user", "content": prompt},
                            ],
                            "max_tokens": 256,
                        },
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    raw = data["choices"][0]["message"]["content"]
                    actual = data.get("model", _s.openrouter_primary_model or "")
                    model_used = f"openrouter/{actual.split('/')[-1].replace(':free', '')}"
                    break
            except Exception as exc:
                log.warning("part_gem_evaluator.openrouter_failed", attempt=attempt, error=str(exc))

    if not raw and _s.ollama_base_url:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{_s.ollama_base_url}/api/chat",
                    json={
                        "model": _s.ollama_model,
                        "messages": [
                            {"role": "system", "content": PART_EVAL_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                raw = resp.json().get("message", {}).get("content")
                model_used = f"ollama/{_s.ollama_model}"
        except Exception as exc:
            log.warning("part_gem_evaluator.ollama_failed", error=str(exc))

    if not raw:
        return None

    return _parse_part_verdict(raw, model_used)


def _parse_part_verdict(raw: str, model_used: str) -> PartGemResult | None:
    match = re.search(r'\{[\s\S]*?\}', raw)
    if not match:
        log.warning("part_gem_evaluator.no_json", raw=raw[:200])
        return None
    try:
        d = json.loads(match.group())
    except json.JSONDecodeError as exc:
        log.warning("part_gem_evaluator.json_error", error=str(exc))
        return None

    verdict = str(d.get("verdict", "REJECT")).upper().strip()
    if verdict not in _VALID_VERDICTS:
        verdict = "REJECT"

    try:
        return PartGemResult(
            verdict=verdict,
            market_price_estimate=float(d.get("market_price_estimate") or 0),
            confidence=min(1.0, max(0.0, float(d.get("confidence") or 0.5))),
            reasoning=str(d.get("reasoning") or ""),
            model_used=model_used,
        )
    except (TypeError, ValueError) as exc:
        log.warning("part_gem_evaluator.field_error", error=str(exc))
        return None
