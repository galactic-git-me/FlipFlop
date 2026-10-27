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
from app.gem_radar.search_identity import SEARCH_IDENTITY_VERSION
from app.gem_radar.cpk_market import upsert_listing_price, upsert_scan_price, remove_listing_price
from app.gem_radar.benchmarks import normalize_match_key
from app.gem_radar.opportunity_scoring import identity_gates
from app.gem_radar.identity import is_full_system_listing, resolve_identity
from app.gem_radar.fan_category import correct_case_fan_cpk
from app.gem_radar.product_identifiers import categories_compatible, extract_asin, identity_conflicts, identity_has_variant_evidence


_ALIAS_CACHE: tuple[float, list[tuple[str, str, dict]]] | None = None
_TITLE_ALIAS_INDEX: dict[tuple, list[tuple[str, dict]]] = {}


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
    global _ALIAS_CACHE, _TITLE_ALIAS_INDEX
    from app.gem_radar.search_identity import last_resort_title_key, unique_title_candidate
    now = time.monotonic()
    if _ALIAS_CACHE is None or now - _ALIAS_CACHE[0] > 600:
        rows = (await db.execute(text("""
            SELECT DISTINCT cpk, cpk_data
            FROM gem_radar_listing_cpk
            WHERE cpk IS NOT NULL AND cpk_data IS NOT NULL
        """))).fetchall()
        aliases: list[tuple[str, str, dict]] = []
        title_index = {}
        for cpk, data in rows:
            data = data or {}
            source_title = data.get('identity_source_title')
            if source_title and (key := last_resort_title_key(source_title, data.get('category'), data)):
                title_index.setdefault(key, []).append((cpk, data))
            for value in (data.get("model"), f"{data.get('brand') or ''}{data.get('model') or ''}"):
                alias = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
                if len(alias) >= 8:
                    aliases.append((alias, cpk, data))
        _ALIAS_CACHE = (now, aliases)
        _TITLE_ALIAS_INDEX = title_index
    if key := last_resort_title_key(title, resolve_identity(title).category):
        if key in _TITLE_ALIAS_INDEX:
            return unique_title_candidate(title, _TITLE_ALIAS_INDEX[key])
    title_key = re.sub(r"[^A-Z0-9]", "", title.upper())
    matches = [(alias, cpk, data) for alias, cpk, data in _ALIAS_CACHE[1]
               if alias in title_key and _valid_existing_cpk(data, title)]
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
    if is_full_system_listing(title) or not data or not data.get("category") or not data.get("brand") or not data.get("model"):
        return False
    evidenced_mpn = (data.get('extraction_method') in {'search_manufacturer_mpn','search_title_fallback'}
                     and any(c.get('kind')=='mpn' and c.get('value')==data.get('model')
                             for c in data.get('identity_claims', [])))
    vetoes = {'accessory_or_parts_listing','bundle_listing'}
    if not evidenced_mpn:
        vetoes.add('identity_incomplete')
    return identity_has_variant_evidence(title, data) and not identity_conflicts(title, data) and not any(
        flag in vetoes
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
    source_url: str | None = None,
    gtin: str | None = None,
    mpn: str | None = None,
    model_number: str | None = None,
    brand: str | None = None,
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
    # A complete PC can mention a CPU model in its title, but its system price
    # must never become a component benchmark. Clear obsolete current aliases
    # as well as prices; retain all source observations and sold history.
    if is_full_system_listing(title):
        await remove_listing_price(db, listing_id)
        await db.execute(text('DELETE FROM gem_radar_listing_cpk WHERE listing_id=:id'), {'id':listing_id})
        await db.execute(text('''UPDATE gem_radar_scored_listings SET cpk=NULL,
            classification='INELIGIBLE',deal_score=0,
            evidence_reason='complete_system_not_component',
            reasoning_summary='Complete computer; excluded from component matching and pricing.'
            WHERE listing_id=:id AND cpk IS NOT NULL'''), {'id':listing_id})
        return None

    existing = await db.execute(
        text("SELECT cpk, cpk_data FROM gem_radar_listing_cpk WHERE listing_id = :listing_id"),
        {"listing_id": listing_id},
    )
    row = existing.fetchone()

    from app.gem_radar.product_identity_registry import resolve_identifiers
    identifier_identity = await resolve_identifiers(db, title=title, category=category,
        brand=brand, gtin=gtin, mpn=mpn, source_url=source_url)
    if identifier_identity and identifier_identity['status']=='conflict':
        await remove_listing_price(db, listing_id)
        if row:
            data={**(row[1] or {}),'identity_status':'conflict','identity_conflict':identifier_identity}
            await db.execute(text('UPDATE gem_radar_listing_cpk SET cpk_data=CAST(:data AS jsonb),updated_at=CURRENT_TIMESTAMP WHERE listing_id=:id'),
                {'id':listing_id,'data':json.dumps(data)})
        return None

    asin = extract_asin(source_url) or extract_asin(listing_id)
    asin_identity = None
    if not identifier_identity and (row is None or not _valid_existing_cpk(row[1], title)):
        if row is not None:
            # Quarantine stale/invalid identity before looking for a trusted
            # identity from an exact marketplace product identifier.
            await remove_listing_price(db, listing_id)
            await db.execute(text("DELETE FROM gem_radar_listing_cpk WHERE listing_id = :listing_id"), {"listing_id": listing_id})
        if asin:
            candidates = (await db.execute(text("""
                SELECT listing_id, cpk, cpk_data, cpk_confidence
                FROM gem_radar_listing_cpk
                WHERE listing_id = :asin OR listing_id ILIKE :asin_pattern
            """), {"asin": asin, "asin_pattern": f"%{asin}%"})).mappings().all()
            valid_candidates = [
                candidate for candidate in candidates
                if extract_asin(candidate["listing_id"]) == asin
                and candidate["listing_id"] != listing_id
                and _valid_existing_cpk(candidate["cpk_data"], title)
                and categories_compatible(category, (candidate["cpk_data"] or {}).get("category"))
            ]
            candidate_cpks = {candidate["cpk"] for candidate in valid_candidates}
            if len(candidate_cpks) == 1:
                candidate = valid_candidates[0]
                asin_identity = (candidate["cpk"], candidate["cpk_data"], candidate["cpk_confidence"])

    if identifier_identity:
        cpk=identifier_identity['cpk'];cpk_data=identifier_identity['data']
        cpk_data['identity_claims']=identifier_identity['claims']
        brand=cpk_data.get('brand');model=cpk_data.get('model');extracted_category=cpk_data.get('category')
        await db.execute(text('''INSERT INTO gem_radar_listing_cpk(listing_id,cpk,cpk_data,cpk_confidence)
            VALUES(:id,:cpk,CAST(:data AS jsonb),1.0)
            ON CONFLICT(listing_id) DO UPDATE SET cpk=EXCLUDED.cpk,cpk_data=EXCLUDED.cpk_data,
              cpk_confidence=EXCLUDED.cpk_confidence,updated_at=CURRENT_TIMESTAMP'''),
            {'id':listing_id,'cpk':cpk,'data':json.dumps(cpk_data)})
    elif row is not None and _valid_existing_cpk(row[1], title) and (
            (row[1] or {}).get('identity_claims')
            or (row[1] or {}).get('identity_validation_version') == SEARCH_IDENTITY_VERSION):
        cpk = row[0]
        cpk_data = row[1] or {}
        brand = cpk_data.get("brand")
        model = cpk_data.get("model")
        extracted_category = cpk_data.get("category")
    elif asin_identity is not None:
        cpk, cpk_data, cpk_confidence = asin_identity
        cpk_data = cpk_data or {}
        brand = cpk_data.get("brand")
        model = cpk_data.get("model")
        extracted_category = cpk_data.get("category") or category
        await db.execute(text("""
            INSERT INTO gem_radar_listing_cpk (listing_id, cpk, cpk_data, cpk_confidence)
            VALUES (:listing_id, :cpk, :cpk_data, :cpk_confidence)
            ON CONFLICT (listing_id) DO UPDATE SET
                cpk = EXCLUDED.cpk, cpk_data = EXCLUDED.cpk_data,
                cpk_confidence = EXCLUDED.cpk_confidence, updated_at = CURRENT_TIMESTAMP
        """), {
            "listing_id": listing_id,
            "cpk": cpk,
            "cpk_data": json.dumps(cpk_data),
            "cpk_confidence": cpk_confidence,
        })
    else:
        alias = await _lookup_unique_catalog_alias(db, title)
        if alias is None and row is not None and _valid_existing_cpk(row[1], title):
            alias = (row[0], row[1])  # Retain a valid known source alias if no better evidence exists.
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
                if identity_conflicts(title, extracted.to_dict(), category) or any(flag != "identity_incomplete" for flag in extracted_flags):
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

    # Cached identities and catalogue aliases can predate the fan guard.
    # Correct the persisted identity before assigning its market-price cohort.
    if extracted_category == "case":
        identity_row = (await db.execute(
            text("SELECT cpk_data FROM gem_radar_listing_cpk WHERE listing_id = :listing_id"),
            {"listing_id": listing_id},
        )).scalar_one_or_none()
        if identity_row:
            corrected_cpk, corrected_data = correct_case_fan_cpk(title, identity_row)
            if corrected_data.get("category") == "fan":
                cpk, extracted_category = corrected_cpk, "fan"
                await db.execute(text("""
                    UPDATE gem_radar_listing_cpk
                    SET cpk = :cpk, cpk_data = :data, updated_at = CURRENT_TIMESTAMP
                    WHERE listing_id = :listing_id
                """), {"cpk": cpk, "data": json.dumps(corrected_data), "listing_id": listing_id})

    # A resighting may skip inference only after this version has validated
    # the same source identity. Price changes do not affect the fingerprint.
    fingerprint=hashlib.sha256(re.sub(r'\s+',' ',title.casefold()).strip().encode()).hexdigest()
    await db.execute(text('''UPDATE gem_radar_listing_cpk SET cpk_data=cpk_data::jsonb || CAST(:marker AS jsonb),
        updated_at=CURRENT_TIMESTAMP WHERE listing_id=:id'''),
        {'id':listing_id,'marker':json.dumps({'identity_validation_version':SEARCH_IDENTITY_VERSION,'identity_title_sha256':fingerprint,'identity_source_title':title})})
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
