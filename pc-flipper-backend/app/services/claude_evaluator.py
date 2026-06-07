"""
Claude Candidate Evaluator — authoritative gem classification via AI.

The enrichment engine (flip_opportunities / listing_ingest_queue) gathers all
the data; this service makes the final call on whether a listing is worth buying.

Output schema (returned as ClaudeEvalResult):
{
  "verdict":             "GEM" | "GOOD" | "MAYBE" | "REJECT",
  "flipability_score":   0-100,
  "expected_profit":     float (£, after all costs + fees),
  "roi":                 float (0.74 = 74% return on capital spent),
  "confidence":          float 0.0-1.0,
  "capital_efficiency":  int 1-10,
  "resale_demand":       int 1-10,
  "upgrade_complexity":  int 1-10 (1=simple, 10=very complex),
  "reasoning":           str (2-3 sentences),
  "main_risk":           str (single biggest risk)
}
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)

EVAL_SYSTEM = """You are an expert PC flipping analyst for a UK-based reseller.
Evaluate whether a second-hand PC listing is worth buying, upgrading, and reselling for profit.

THE FLIP MODEL:
1. Buy a used PC cheap (ideally £50-£250)
2. Upgrade: add RTX 3060 12GB if no GPU (~£185 cost, adds ~£240 to resale); add 1TB NVMe SSD if missing (~£65 cost, adds ~£70); upgrade to 32GB DDR4 if < 32GB (~£65 cost, adds ~£60); add themed RGB gaming case always (~£70 cost, adds ~£140 — 2× rule)
3. Sell fully upgraded themed PC on eBay (~12.7% fees)
4. Presentation premium: ~£75 added to resale for clean tested build

PLATFORM CONTEXT (UK 2025/26):
- Total upgrade cost with no GPU/storage/RAM: ~£385 + buy price + case
- AM5 platform (Ryzen 7000): add £200 overhead (B650 mobo + DDR5 kit)
- Sweet spot: Intel i5/i7 8th–13th gen OR AMD Ryzen 5000 (AM4), no GPU, £50–£200

SWEET SPOTS (buy immediately if priced right):
- HP EliteDesk / Dell OptiPlex / Lenovo ThinkCentre — workstation gold
- i5/i7/i9 with no GPU and no storage — maximum upgrade margin
- "No GPU, no storage" bundle at £80–150 — near-guaranteed £150+ profit
- Ryzen 5 5600X / 5700X no-GPU at under £180

RED FLAGS (reduce score heavily):
- Ryzen 7000 / AM5: £200 platform overhead kills margins unless very cheap
- Already has GPU + SSD: seller has priced in the upgrade value
- Refurb shop / IT reseller listing: they know market value, no margin left
- Price > £350: capital risk — needs exceptional specs to justify
- "For parts" / genuinely faulty / no PSU on non-tower: avoid unless very cheap
- Seller type: refurb_shop — they've already priced in flip margin

VERDICT THRESHOLDS:
- GEM:    flipability_score ≥ 70 AND expected_profit ≥ £150 — act immediately
- GOOD:   flipability_score ≥ 45 AND expected_profit ≥ £80  — solid flip
- MAYBE:  marginal — monitor but no immediate action needed
- REJECT: bad economics, too risky, margin gone, or component-only

Respond with ONLY valid JSON — no explanation, no markdown, no extra text:
{
  "verdict": "GEM",
  "flipability_score": 85,
  "expected_profit": 195,
  "roi": 0.82,
  "confidence": 0.88,
  "capital_efficiency": 9,
  "resale_demand": 8,
  "upgrade_complexity": 3,
  "reasoning": "i7-9700 workstation at £120 with no GPU or storage. Standard upgrade path applies cleanly. Strong demand for this generation on eBay.",
  "main_risk": "Condition unknown — 'untested' in title introduces risk of hidden fault."
}"""

_VALID_VERDICTS = {"GEM", "GOOD", "MAYBE", "REJECT"}


@dataclass
class ClaudeEvalResult:
    verdict: str
    flipability_score: float
    expected_profit: float
    roi: float
    confidence: float
    capital_efficiency: int
    resale_demand: int
    upgrade_complexity: int
    reasoning: str
    main_risk: str
    model_used: str


def _build_prompt(d: dict) -> str:
    lines = [
        "LISTING TO EVALUATE:",
        f"  Title:       {d.get('title', '?')}",
        f"  Price:       £{d.get('price', 0):.0f}",
        f"  Source:      {d.get('source_name', '?')}",
        f"  Location:    {d.get('location') or 'not stated'}",
        f"  Condition:   {d.get('condition') or 'not stated'}",
        f"  Seller type: {d.get('seller_type') or 'unknown'}",
        f"  Listing type:{d.get('listing_type') or 'buy_it_now'}",
        "",
        "PARSED SPECS:",
        f"  CPU:     {d.get('cpu') or 'unknown'}",
        f"  RAM:     {d.get('ram_gb') or '?'}GB {d.get('ram_type') or ''}",
        f"  Storage: {d.get('storage_gb') or 'none'} {d.get('storage_type') or ''}",
        f"  GPU:     {d.get('gpu') or 'none / missing'}",
        f"  Has PSU: {'yes' if d.get('has_psu') else 'no'}",
        "",
        "MARKET COMPS:",
        f"  Sold comps (n={d.get('resale_comp_count', 0)}):",
        f"    25th pct (low):  £{d.get('resale_low') or 0:.0f}",
        f"    Median:          £{d.get('estimated_resale') or 0:.0f}",
        f"    75th pct (high): £{d.get('resale_high') or 0:.0f}",
        "",
        "COST MODEL (rule-based estimate):",
        f"  Upgrade cost:       £{d.get('estimated_upgrade_cost') or 0:.0f}",
        f"  Estimated profit:   £{d.get('estimated_profit') or 0:.0f}  (median resale scenario)",
        "",
        "RULE-BASED PRE-SCORE:",
        f"  Score:   {d.get('gem_score') or 0:.1f}/100",
        f"  Signals: {', '.join(d.get('gem_signals') or []) or 'none'}",
    ]
    desc = (d.get("description") or "").strip()
    if desc:
        lines += ["", f"DESCRIPTION (first 400 chars): {desc[:400]}"]
    return "\n".join(lines)


async def evaluate_listing(listing_data: dict) -> ClaudeEvalResult | None:
    """
    Send listing data to the best available AI and return a structured verdict.
    Returns None if all backends fail.
    """
    from app.config import get_settings
    _s = get_settings()

    prompt = _build_prompt(listing_data)
    messages = [{"role": "user", "content": prompt}]
    raw: str | None = None
    model_used = "none"

    # 1 — Ollama local (primary — no rate limits, no cost)
    if _s.ollama_base_url:
        try:
            import httpx
            async with httpx.AsyncClient(timeout=180) as client:
                resp = await client.post(
                    f"{_s.ollama_base_url}/api/chat",
                    json={
                        "model": _s.ollama_model,
                        "messages": [
                            {"role": "system", "content": EVAL_SYSTEM},
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                    },
                )
                resp.raise_for_status()
                raw = resp.json().get("message", {}).get("content")
                model_used = f"ollama/{_s.ollama_model}"
        except Exception as exc:
            log.warning("claude_evaluator.ollama_failed", error=str(exc), exc_type=type(exc).__name__)

    # 2 — Anthropic cloud fallback
    if not raw and _s.anthropic_api_key:
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=_s.anthropic_api_key)
            resp = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                system=EVAL_SYSTEM,
                messages=messages,
            )
            raw = resp.content[0].text if resp.content else None
            model_used = "claude-haiku-4-5"
        except Exception as exc:
            log.warning("claude_evaluator.anthropic_failed", error=str(exc))

    # 3 — OpenRouter fallback (with exponential backoff on 429)
    if not raw and _s.openrouter_api_key:
        import httpx
        for attempt in range(4):
            try:
                wait = (2 ** attempt) * 5  # 5s, 10s, 20s, 40s
                if attempt > 0:
                    await asyncio.sleep(wait)
                async with httpx.AsyncClient(timeout=60) as client:
                    resp = await client.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {_s.openrouter_api_key}",
                            "HTTP-Referer": "http://localhost:3000",
                            "X-Title": "PC Flipper Gem Evaluator",
                        },
                        json={
                            "model": _s.openrouter_primary_model or "google/gemma-4-31b-it:free",
                            "messages": [
                                {"role": "system", "content": EVAL_SYSTEM},
                                {"role": "user", "content": prompt},
                            ],
                            "max_tokens": 512,
                        },
                    )
                    if resp.status_code == 429:
                        retry_after = int(resp.headers.get("Retry-After", wait))
                        log.warning("claude_evaluator.openrouter_rate_limited", attempt=attempt, retry_after=retry_after)
                        await asyncio.sleep(retry_after)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    raw = data["choices"][0]["message"]["content"]
                    actual = data.get("model", _s.openrouter_primary_model or "")
                    model_used = f"openrouter/{actual.split('/')[-1].replace(':free', '')}"
                    break
            except Exception as exc:
                log.warning("claude_evaluator.openrouter_failed", attempt=attempt, error=str(exc))
                if attempt == 3:
                    break

    if not raw:
        return None

    return _parse_verdict(raw, model_used)


def _parse_verdict(raw: str, model_used: str) -> ClaudeEvalResult | None:
    match = re.search(r'\{[\s\S]*?\}', raw)
    if not match:
        log.warning("claude_evaluator.no_json", raw=raw[:200])
        return None
    try:
        d = json.loads(match.group())
    except json.JSONDecodeError as exc:
        log.warning("claude_evaluator.json_error", error=str(exc), raw=raw[:200])
        return None

    verdict = str(d.get("verdict", "REJECT")).upper().strip()
    if verdict not in _VALID_VERDICTS:
        verdict = "REJECT"

    try:
        return ClaudeEvalResult(
            verdict=verdict,
            flipability_score=min(100.0, max(0.0, float(d.get("flipability_score") or 0))),
            expected_profit=float(d.get("expected_profit") or 0),
            roi=float(d.get("roi") or 0),
            confidence=min(1.0, max(0.0, float(d.get("confidence") or 0.5))),
            capital_efficiency=max(1, min(10, int(d.get("capital_efficiency") or 5))),
            resale_demand=max(1, min(10, int(d.get("resale_demand") or 5))),
            upgrade_complexity=max(1, min(10, int(d.get("upgrade_complexity") or 5))),
            reasoning=str(d.get("reasoning") or ""),
            main_risk=str(d.get("main_risk") or ""),
            model_used=model_used,
        )
    except (TypeError, ValueError) as exc:
        log.warning("claude_evaluator.field_error", error=str(exc))
        return None
