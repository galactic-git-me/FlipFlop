"""TEST script (writes nothing to the database): batch-sends still-
unclassified listing titles to an LLM via OpenRouter (the same provider
claude_screening.py already uses for GEM/SUPER_GEM deep-research screening)
and asks it to (a) flag genuine junk vs real PC components, and (b) produce
the same canonical_model_id format claude_screening.py already assigns to
GEM/SUPER_GEM listings, for anything genuine.

This answers two questions before deciding whether to wire this into the
live pipeline: how much of the regex-unclassifiable "category=None" bucket
is actually junk vs real hardware, and of the real hardware, how many can
actually get priced -- either against pre-existing comps in the historical
index, or against each other (since several differently-worded listings of
the same rare product, e.g. "AMD EPYC 9634", can only ever price each other
once normalized to the same key -- regex never groups them at all).

Usage:
    python scripts/llm_identity_test.py [--limit 300] [--batch-size 40]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter, defaultdict

sys.path.insert(0, ".")

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.gem_radar.benchmarks import fetch_bin_benchmarks, normalize_match_key
from app.gem_radar.claude_screening import _openrouter_tool_call
from app.gem_radar.pipeline import build_batch_price_index
from app.models.gem_radar_scored_listing import GemRadarScoredListing

# Ollama Cloud model (via the locally-running ollama daemon's cloud tunnel)
# used as a fallback tier when OpenRouter's free-tier model is rate-limited
# -- confirmed reachable and responsive on this machine. Ollama doesn't
# reliably support forced tool-calling across all models, so this tier asks
# for a raw JSON array via format="json" mode instead, same technique
# claude_screening.py's _screen_via_ollama already uses.
_OLLAMA_FALLBACK_MODEL = "deepseek-v4-flash:cloud"

_KNOWN_CATEGORIES = ["cpu", "gpu", "ram", "ssd", "motherboard", "psu", "cooler", "fan", "case"]

_TOOL_SCHEMA = {
    "name": "submit_identity_mapping",
    "description": "Classify and normalize a batch of numbered listing titles.",
    "input_schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "index": {"type": "integer", "description": "The listing's number as given."},
                        "is_pc_component": {
                            "type": "boolean",
                            "description": (
                                "True ONLY if this is a genuine, standalone PC hardware component "
                                "(CPU, GPU, RAM, storage/SSD, motherboard, PSU, cooler, case, or case "
                                "fan) being sold as itself. False for accessories, cables, brackets, "
                                "mounting hardware, heatsink pads, books, unrelated products, full "
                                "prebuilt systems, laptops, or multi-item bundle/lot listings without a "
                                "single specific model."
                            ),
                        },
                        "category": {
                            "type": ["string", "null"],
                            "enum": _KNOWN_CATEGORIES + [None],
                            "description": "One of the fixed category list, or null if is_pc_component is false.",
                        },
                        "canonical_model_id": {
                            "type": ["string", "null"],
                            "description": (
                                "STABLE matching key '<BRAND> <MODEL>' in uppercase, brand and model "
                                "number ONLY -- no core/thread counts, clock speeds, socket names, "
                                "coolers, or filler words like CPU/Processor/Desktop. Two listings for "
                                "the same real product, worded completely differently, must produce "
                                "the IDENTICAL string. Null if not identifiable or not a PC component."
                            ),
                        },
                    },
                    "required": ["index", "is_pc_component", "category", "canonical_model_id"],
                },
            },
        },
        "required": ["results"],
    },
}

_SYSTEM_PROMPT = """You are a product-identity classification assistant for a PC-component deal-sourcing tool.

You will be given a numbered list of eBay/marketplace listing titles that a regex-based classifier could
NOT identify. For EACH numbered listing, decide:

1. is_pc_component: true only if the title is a genuine, standalone PC hardware component (CPU, GPU, RAM,
   SSD/storage, motherboard, PSU, cooler, case, or case fan) being sold as itself. Mark false for
   accessories, cables, mounting brackets, heatsink pads, packaging, books, completely unrelated products,
   full prebuilt PCs/laptops, or lot/bundle listings that don't name one specific model.
2. category: one of cpu/gpu/ram/ssd/motherboard/psu/cooler/fan/case if is_pc_component is true, else null.
3. canonical_model_id: a STABLE "<BRAND> <MODEL>" matching key in uppercase -- brand and exact model number
   only, no filler words (CPU/Processor/Desktop/Cores/GHz/socket names/etc). The critical test: two
   listings of the SAME real product, worded completely differently, MUST produce the IDENTICAL string.
   Examples: "AMD EPYC 9634 Processor 2.25 GHz 384MB L3 Cache - Tray" -> "AMD EPYC 9634". "Intel Xeon Gold
   6252 CPU Processor 24 Core" -> "INTEL XEON GOLD 6252". Null if not identifiable or not a PC component.

You MUST NOT state, estimate, or imply any price or market value.

Call submit_identity_mapping with one entry per numbered listing, in any order, covering every index given."""


def _build_batch_prompt(batch: list[tuple[str, str]]) -> str:
    lines = [f'{i}. "{title}"' for i, (_listing_id, title) in enumerate(batch, start=1)]
    return "Classify these listings:\n\n" + "\n".join(lines)


async def _classify_batch_via_ollama(
    batch: list[tuple[str, str]], model: str = _OLLAMA_FALLBACK_MODEL, timeout: float = 600.0
) -> dict | None:
    prompt = _build_batch_prompt(batch)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            # No forced tool schema on this path (unlike OpenRouter), so the
                            # exact JSON keys must be spelled out explicitly -- without this
                            # a model will happily invent its own reasonable-but-different
                            # field names (observed: "listing_id" instead of "index").
                            "content": _SYSTEM_PROMPT
                            + '\n\nRespond with ONLY a single JSON object: {"results": [{"index": <int>, '
                            '"is_pc_component": <bool>, "category": <string or null>, '
                            '"canonical_model_id": <string or null>}, ...]}. One entry per numbered '
                            "listing, using exactly these field names. No other text.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "format": "json",
                    "stream": False,
                },
            )
            resp.raise_for_status()
            content = resp.json().get("message", {}).get("content")
            return json.loads(content) if content else None
    except Exception as exc:
        print(f"  (ollama batch failed: {exc!r})")
        return None


async def _classify_batch(
    settings, batch: list[tuple[str, str]], max_retries: int = 2, provider: str = "auto",
    ollama_model: str = _OLLAMA_FALLBACK_MODEL, ollama_timeout: float = 600.0,
) -> dict[str, dict]:
    """batch: list of (listing_id, title). Returns {listing_id: {is_pc_component, category, canonical_model_id}}.

    provider: "auto" (openrouter, falling back to ollama), "openrouter" only,
    or "ollama" only -- lets a single backend be isolated for comparison."""
    data = None
    if provider in ("auto", "openrouter"):
        prompt = _build_batch_prompt(batch)
        data = await _openrouter_tool_call(
            settings, _SYSTEM_PROMPT, prompt, _TOOL_SCHEMA, max_tokens=4096, max_retries=max_retries
        )
        if data is None and provider == "auto":
            print("  (openrouter failed for this batch, falling back to ollama)")
    if data is None and provider in ("auto", "ollama"):
        data = await _classify_batch_via_ollama(batch, model=ollama_model, timeout=ollama_timeout)
    out: dict[str, dict] = {}
    if data is None:
        return out
    for item in data.get("results", []) or []:
        try:
            idx = int(item["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (1 <= idx <= len(batch)):
            continue
        listing_id, _title = batch[idx - 1]
        canonical = str(item.get("canonical_model_id") or "").strip().upper() or None
        out[listing_id] = {
            "is_pc_component": bool(item.get("is_pc_component", False)),
            "category": item.get("category"),
            "canonical_model_id": canonical,
        }
    return out


def _chunks(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _bucket_for_condition(condition: str | None) -> str | None:
    if condition in ("new", "new_other"):
        return "new"
    if condition in ("used", "refurbished"):
        return "used"
    return None


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=300, help="Max listings to test (default 300).")
    parser.add_argument("--batch-size", type=int, default=40, help="Titles per LLM request (default 40).")
    parser.add_argument("--concurrency", type=int, default=3, help="Concurrent LLM requests (default 3).")
    parser.add_argument(
        "--provider", choices=["auto", "openrouter", "ollama"], default="auto",
        help="Force a single backend instead of the openrouter->ollama fallback chain (default auto).",
    )
    parser.add_argument(
        "--ollama-model", default=_OLLAMA_FALLBACK_MODEL,
        help=f"Ollama model tag to use when provider is ollama/auto (default {_OLLAMA_FALLBACK_MODEL}).",
    )
    parser.add_argument(
        "--ollama-timeout", type=float, default=600.0,
        help="Per-request timeout in seconds for the ollama tier (default 600 -- local reasoning models can be slow).",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.provider in ("auto", "openrouter") and not settings.openrouter_api_key:
        print("No OPENROUTER_API_KEY configured -- nothing to test with.")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                GemRadarScoredListing.listing_id,
                GemRadarScoredListing.title,
                GemRadarScoredListing.condition,
                GemRadarScoredListing.delivered_price,
            )
            .where(
                GemRadarScoredListing.market_new_price.is_(None),
                GemRadarScoredListing.market_used_price.is_(None),
                GemRadarScoredListing.category.is_(None),
                GemRadarScoredListing.source != "vinted",
            )
            .order_by(GemRadarScoredListing.id)
            .limit(args.limit)
        )
        rows = result.all()
        print(f"Testing against {len(rows)} still-unclassified listings\n")

        row_by_id = {r.listing_id: r for r in rows}
        batches = _chunks([(r.listing_id, r.title) for r in rows], args.batch_size)

        sem = asyncio.Semaphore(args.concurrency)

        async def _run(batch):
            async with sem:
                return await _classify_batch(
                    settings, batch, provider=args.provider, ollama_model=args.ollama_model, ollama_timeout=args.ollama_timeout
                )

        backend_desc = args.ollama_model if args.provider == "ollama" else settings.openrouter_primary_model
        print(f"Sending {len(batches)} batches ({args.batch_size} titles each) via provider={args.provider} ({backend_desc})...")
        batch_results = await asyncio.gather(*[_run(b) for b in batches])
        classified: dict[str, dict] = {}
        for br in batch_results:
            classified.update(br)

        failed_count = len(rows) - len(classified)
        junk = {lid: c for lid, c in classified.items() if not c["is_pc_component"]}
        genuine = {lid: c for lid, c in classified.items() if c["is_pc_component"]}
        genuine_with_key = {lid: c for lid, c in genuine.items() if c["canonical_model_id"]}

        print(f"\nLLM did not return a result for: {failed_count} listings (provider/parse failures)")
        print(f"Classified as junk/not-a-component: {len(junk)}")
        print(f"Classified as genuine PC component: {len(genuine)} (of which {len(genuine_with_key)} got a canonical_model_id)")

        print("\nCategory breakdown of genuine components:")
        cat_counts = Counter(c["category"] for c in genuine.values())
        for cat, cnt in cat_counts.most_common():
            print(f"  {str(cat):14s} {cnt}")

        # Build the existing historical/current price index (same as backfill_bin_prices.py)
        print("\nBuilding existing historical price index...")
        existing_index = await build_batch_price_index(db, [])

        # Build a self-referential pool from JUST the newly-classified genuine
        # listings, keyed the same way (normalize_match_key(canonical_model_id))
        # -- this is what lets several differently-worded listings of the same
        # rare product (which regex could never group) price each other for
        # the first time.
        self_index: dict[str, dict[str, list[tuple[str, float]]]] = defaultdict(lambda: {"new": [], "used": []})
        for lid, c in genuine_with_key.items():
            row = row_by_id[lid]
            bucket = _bucket_for_condition(row.condition)
            if bucket is None:
                continue
            self_index[normalize_match_key(c["canonical_model_id"])][bucket].append((lid, row.delivered_price))

        priced = 0
        priced_from_self_only = 0
        canonical_id_counts: Counter[str] = Counter()
        for lid, c in genuine_with_key.items():
            row = row_by_id[lid]
            key = normalize_match_key(c["canonical_model_id"])
            canonical_id_counts[c["canonical_model_id"]] += 1

            existing_entries = existing_index.get(key)
            self_entries = self_index.get(key)
            merged = None
            if existing_entries and self_entries:
                merged = {
                    b: existing_entries.get(b, []) + self_entries.get(b, []) for b in ("new", "used")
                }
            else:
                merged = existing_entries or self_entries

            new_bin, used_bin = fetch_bin_benchmarks(row.condition or "unknown", "exact_model_variant", merged, lid)
            relevant = new_bin if (row.condition or "") in ("new", "new_other") else used_bin
            if relevant.status == "ok":
                priced += 1
                if not existing_entries and self_entries:
                    priced_from_self_only += 1

        print(f"\nOf {len(genuine_with_key)} genuine components with a canonical_model_id:")
        print(f"  Found a real price match: {priced} ({priced/len(genuine_with_key)*100:.1f}%)" if genuine_with_key else "  (none to price)")
        print(f"    ...of which ONLY findable by pooling against each other (not pre-existing comps): {priced_from_self_only}")

        print("\nTop canonical_model_id clusters found in this batch (>=2 listings):")
        for cid, cnt in canonical_id_counts.most_common(20):
            if cnt >= 2:
                print(f"  {cnt:3d}x  {cid}")

        print("\nSample junk classifications (first 15):")
        for lid, c in list(junk.items())[:15]:
            print(f"  {row_by_id[lid].title[:80]}")

        print("\nSample genuine-but-unpriced classifications (first 15):")
        unpriced_genuine = [
            (lid, c) for lid, c in genuine_with_key.items()
            if normalize_match_key(c["canonical_model_id"]) not in existing_index
            and len(self_index.get(normalize_match_key(c["canonical_model_id"]), {}).get("new", []))
            + len(self_index.get(normalize_match_key(c["canonical_model_id"]), {}).get("used", [])) < 2
        ][:15]
        for lid, c in unpriced_genuine:
            print(f"  [{c['category']}] {c['canonical_model_id']!r:35} | {row_by_id[lid].title[:70]}")


if __name__ == "__main__":
    asyncio.run(main())
