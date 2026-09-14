"""Phase 1 of the CPK-driven market-price system, wired into LIVE ingestion
(app/api/gem_radar.py's _submit_scan_body — called for every listing the
FlipFlopXtension submits, the only source of listing data this backend
has). This is deliberately the entire ingestion pipeline now: no eBay/vendor
polling, no scoring, no classification — those are Phase 2's job, and only
run in bulk once the extension signals a whole scan sweep is complete (see
deal_classification.py and the /scan-sweep-complete endpoint).

scripts/phase1_accumulate_cpk_prices.py reuses this same function as an
offline backfill tool for historical observations — the logic lives here
once, not duplicated between the live path and the CLI script.
"""
from __future__ import annotations

import json
import hashlib
import re
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.gem_radar.cpk_extractor import extract_cpk
from app.gem_radar.cpk_market import upsert_listing_price, upsert_scan_price
from app.gem_radar.benchmarks import normalize_match_key
from app.gem_radar.opportunity_scoring import identity_gates
from app.gem_radar.identity import resolve_identity


_ALIAS_CACHE: tuple[float, list[tuple[str, str, dict]]] | None = None


def _deterministic_identity(title: str, category: str | None, price: float | None) -> tuple[str, dict] | None:
    """Build a conservative CPK when the title is unambiguous.

    This is deliberately attempted before the LLM.  A model endpoint outage
    must not turn every recognisable CPU/GPU/RAM/SSD title into
    IDENTITY_FAILED; the resolver already has category-specific patterns and
    the same hard identity vetoes are applied before accepting the result.
    """
    resolved = resolve_identity(title, delivered_price=price)
    resolved_category = (resolved.category or category or "").lower()
    brand = (resolved.brand or "").strip().lower()
    model = re.sub(r"[^a-z0-9]+", "-", (resolved.model or "").lower()).strip("-")
    if not resolved_category or not brand or not model:
        return None
    data = {"category": resolved_category, "brand": brand, "model": model, "specs": {}, "confidence": resolved.exact_sku_confidence}
    if any(flag != "identity_incomplete" for flag in identity_gates(title, data)):
        return None
    cpk = hashlib.sha256(f"{resolved_category}|{brand}|{model}".encode()).hexdigest()[:16]
    data["cpk"] = cpk
    return cpk, data


async def _lookup_unique_catalog_alias(db: AsyncSession, title: str) -> tuple[str, dict] | None:
    """Resolve a title from the existing CPK catalog without an LLM call.

    Only the longest matching model/brand+model aliases are considered, and a
    match is accepted only when all matching aliases point to one CPK. This
    recovers clear products while refusing board-partner and generic-memory
    collisions such as RX6800XT16GB or 16GBDDR4.
    """
    global _ALIAS_CACHE
    now = time.monotonic()
    if _ALIAS_CACHE is None or now - _ALIAS_CACHE[0] > 600:
        rows = (await db.execute(text("""
            SELECT DISTINCT cpk, cpk_data
            FROM gem_radar_listing_cpk
            WHERE cpk IS NOT NULL AND cpk_data IS NOT NULL
        """))).fetchall()
        aliases: list[tuple[str, str, dict]] = []
        for cpk, data in rows:
            data = data or {}
            for value in (data.get("model"), f"{data.get('brand') or ''}{data.get('model') or ''}"):
                alias = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
                if len(alias) >= 8:
                    aliases.append((alias, cpk, data))
        _ALIAS_CACHE = (now, aliases)
    title_key = re.sub(r"[^A-Z0-9]", "", title.upper())
    matches = [(alias, cpk, data) for alias, cpk, data in _ALIAS_CACHE[1] if alias in title_key]
    if not matches:
        return None
    longest = max(len(alias) for alias, _, _ in matches)
    cpks = {cpk for alias, cpk, _ in matches if len(alias) == longest}
    if len(cpks) != 1:
        return None
    cpk = next(iter(cpks))
    return cpk, next(data for alias, candidate, data in matches if len(alias) == longest and candidate == cpk)


def _identity_match_keys(brand: str | None, model: str | None) -> set[str]:
    """Exact sold-search keys that can safely inherit this CPK."""
    keys = {normalize_match_key(model or ""), normalize_match_key(f"{brand or ''} {model or ''}")}
    return {key for key in keys if len(key) >= 5}


def _valid_existing_cpk(data: dict | None, title: str) -> bool:
    if not data or not data.get("category") or not data.get("brand") or not data.get("model"):
        return False
    return not any(
        flag in {"identity_incomplete", "accessory_or_parts_listing", "bundle_listing"}
        for flag in identity_gates(title, data)
    )


async def assign_cpk_and_accumulate_price(
    db: AsyncSession,
    listing_id: str,
    title: str,
    category: str | None,
    condition: str | None,
    price: float | None,
    scan_price: float | None = None,
) -> str | None:
    """Looks up (or extracts, via one LLM call if genuinely new) this
    listing's CPK, persists it to gem_radar_listing_cpk, and folds its price
    into that CPK's market-price aggregate (gem_radar_cpk_market_price via
    cpk_market.upsert_listing_price). If scan_price is provided, records it
    as a scan observation for cross-vendor market aggregation.
    Returns the CPK, or None if extraction failed or was too low-confidence to
    trust (e.g. not a recognisable PC component) — the listing still gets its
    observation row regardless via the caller, it just never gets folded into
    any CPK's market price.
    """
    existing = await db.execute(
        text("SELECT cpk, cpk_data FROM gem_radar_listing_cpk WHERE listing_id = :listing_id"),
        {"listing_id": listing_id},
    )
    row = existing.fetchone()

    if row is not None and _valid_existing_cpk(row[1], title):
        cpk = row[0]
        cpk_data = row[1] or {}
        brand = cpk_data.get("brand")
        model = cpk_data.get("model")
        extracted_category = cpk_data.get("category")
    else:
        if row is not None:
            # Quarantine stale/invalid identity before re-extraction; prices
            # tied to it are removed so it cannot contaminate another cohort.
            await db.execute(text("DELETE FROM gem_radar_cpk_listing_price WHERE listing_id = :listing_id"), {"listing_id": listing_id})
            await db.execute(text("DELETE FROM gem_radar_listing_cpk WHERE listing_id = :listing_id"), {"listing_id": listing_id})
        alias = await _lookup_unique_catalog_alias(db, title)
        if alias is not None:
            cpk, alias_data = alias
            brand = alias_data.get("brand")
            model = alias_data.get("model")
            extracted_category = alias_data.get("category") or category
            await db.execute(text("""
                INSERT INTO gem_radar_listing_cpk (listing_id, cpk, cpk_data, cpk_confidence)
                VALUES (:listing_id, :cpk, :cpk_data, :cpk_confidence)
                ON CONFLICT (listing_id) DO UPDATE SET
                    cpk = EXCLUDED.cpk, cpk_data = EXCLUDED.cpk_data,
                    cpk_confidence = EXCLUDED.cpk_confidence, updated_at = CURRENT_TIMESTAMP
            """), {"listing_id": listing_id, "cpk": cpk, "cpk_data": json.dumps(alias_data), "cpk_confidence": 0.9})
        else:
            preflight_flags = identity_gates(title, {"category": category, "brand": "pending", "model": "pending"})
            if any(flag in {"accessory_or_parts_listing", "bundle_listing"} for flag in preflight_flags):
                return None
            deterministic = _deterministic_identity(title, category, price)
            if deterministic is not None:
                cpk, deterministic_data = deterministic
                brand = deterministic_data["brand"]
                model = deterministic_data["model"]
                extracted_category = deterministic_data["category"]
                await db.execute(
                    text(
                        """
                        INSERT INTO gem_radar_listing_cpk (listing_id, cpk, cpk_data, cpk_confidence)
                        VALUES (:listing_id, :cpk, :cpk_data, :cpk_confidence)
                        ON CONFLICT (listing_id) DO UPDATE SET
                            cpk = EXCLUDED.cpk, cpk_data = EXCLUDED.cpk_data,
                            cpk_confidence = EXCLUDED.cpk_confidence, updated_at = CURRENT_TIMESTAMP
                        """
                    ),
                    {"listing_id": listing_id, "cpk": cpk, "cpk_data": json.dumps(deterministic_data), "cpk_confidence": deterministic_data["confidence"]},
                )
                extracted = None
            else:
                extracted = await extract_cpk(title, category, condition)
            if extracted is None:
                if deterministic is None:
                    return None
            else:
                extracted_flags = identity_gates(title, extracted.to_dict())
                if any(flag != "identity_incomplete" for flag in extracted_flags):
                    return None

                await db.execute(
                    text(
                        """
                    INSERT INTO gem_radar_listing_cpk (listing_id, cpk, cpk_data, cpk_confidence)
                    VALUES (:listing_id, :cpk, :cpk_data, :cpk_confidence)
                    ON CONFLICT (listing_id) DO UPDATE SET
                        cpk = EXCLUDED.cpk,
                        cpk_data = EXCLUDED.cpk_data,
                        cpk_confidence = EXCLUDED.cpk_confidence,
                        updated_at = CURRENT_TIMESTAMP
                    """
                    ),
                    {
                        "listing_id": listing_id,
                        "cpk": extracted.cpk,
                        "cpk_data": json.dumps(extracted.to_dict()),
                        "cpk_confidence": extracted.confidence,
                    },
                )
                cpk = extracted.cpk
                brand = extracted.brand
                model = extracted.model
                extracted_category = extracted.category

    match_key = normalize_match_key(title)

    if price is not None:
        await upsert_listing_price(
            db,
            cpk=cpk,
            listing_id=listing_id,
            price=price,
            category=extracted_category or category,
            brand=brand,
            model=model,
        )

    if scan_price is not None:
        await upsert_scan_price(
            db,
            cpk=cpk,
            match_key=match_key,
            price=scan_price,
            category=extracted_category or category,
            brand=brand,
            model=model,
        )

    # Backfill old sold rows only when the normalised alias resolves to one
    # canonical product. A broad text-key update can merge board partners,
    # memory kits, or product families into one realised-price cohort.
    identity_keys = _identity_match_keys(brand, model)
    safe_keys = set()
    for key in {match_key, *identity_keys}:
        candidates = (await db.execute(text("""
            SELECT DISTINCT cpk
            FROM gem_radar_listing_cpk
            WHERE regexp_replace(upper(coalesce(cpk_data->>'model', '')), '[^A-Z0-9]', '', 'g') = :key
               OR regexp_replace(upper(coalesce(cpk_data->>'brand', '') || coalesce(cpk_data->>'model', '')), '[^A-Z0-9]', '', 'g') = :key
        """), {"key": key})).scalars().all()
        if len(set(candidates)) == 1 and candidates[0] == cpk:
            safe_keys.add(key)
    if safe_keys:
        await db.execute(text("""
            UPDATE gem_radar_sold_observations
            SET cpk = :cpk, updated_at = now()
            WHERE match_key = ANY(:keys) AND cpk IS NULL
        """), {"cpk": cpk, "keys": list(safe_keys)})

    return cpk
