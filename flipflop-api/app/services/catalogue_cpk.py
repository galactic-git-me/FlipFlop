"""Keep active catalogue products linked to their cross-vendor CPK identity.

ASIN is the exact Amazon product key. When it has no valid CPK, use an existing
specific identity, deterministic title resolution, then a local-only Qwen
fallback guarded by category, title and variant checks. Unresolved rows remain
unlinked rather than receiving a speculative identity. Catalogue status,
customer price and supplier evidence are not changed.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.gem_radar.cpk_pipeline import _deterministic_identity
from app.gem_radar.identity import resolve_identity
from app.gem_radar.opportunity_scoring import identity_gates
from app.gem_radar.product_identifiers import categories_compatible, extract_asin
from app.gem_radar.cpk_extractor import extract_cpk
from app.config import get_settings


_ROLE_CATEGORIES = {
    "cpu": {"cpu"},
    "gpu": {"gpu"},
    "motherboard": {"motherboard"},
    "ram": {"ram"},
    "storage": {"ssd", "storage"},
    "storage_secondary": {"ssd", "storage"},
    "psu": {"psu"},
    "cooling": {"cooler", "cooling"},
    "case": {"case"},
}
_GENERIC_MODELS = {"", "unknown", "undefined", "component", "chassis", "product", "thermalright"}
_GENERIC_BRANDS = {"", "unknown", "undefined", "mixed-brand", "generic", "unbranded"}
_GENERIC_CASE_MODEL_TOKENS = {
    "atx", "case", "chassis", "computer", "full", "gaming", "itx", "matx", "mid",
    "mini", "pc", "tower", "white", "black", "rgb", "argb", "glass",
}


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").casefold()).strip("-")


def identity_is_usable(title: str, data: dict, roles: set[str]) -> bool:
    from app.gem_radar.product_identifiers import identity_conflicts, identity_has_variant_evidence
    if not identity_has_variant_evidence(title, data) or identity_conflicts(title, data):
        return False
    category = str(data.get("category") or "").casefold()
    brand = _normalise(data.get("brand"))
    model = _normalise(data.get("model"))
    if not category or not brand or not model or brand in _GENERIC_BRANDS or model in _GENERIC_MODELS:
        return False
    if not any(categories_compatible(category, role_category)
               for role in roles for role_category in _ROLE_CATEGORIES.get(role, {role})):
        return False
    if "case" in roles:
        # Broad CPKs such as brand=APNX Creator C1 ChromaFlair, model=mid_tower_case
        # otherwise pass because every case title contains "tower" and "case".
        # A case identity must carry an actual model token in the model field.
        case_model_tokens = [token for token in _normalise(data.get("model") or "").split("-")
                             if token not in _GENERIC_CASE_MODEL_TOKENS]
        if not case_model_tokens or not all(token in re.sub(r"[^a-z0-9]", "", title.casefold())
                                             for token in case_model_tokens):
            return False
    # Exact ASIN is a strong product link, but it cannot repair a CPK that is
    # itself a family/accessory/bundle identity. Ignore only incomplete-data
    # warnings here; all substantive identity vetoes remain blocking.
    flags = identity_gates(title, data)
    if any(flag != "identity_incomplete" for flag in flags):
        return False
    if (data.get('extraction_method') in {'search_manufacturer_mpn','search_title_fallback'}
            and any(claim.get('kind') == 'mpn' and claim.get('value') == data.get('model')
                    for claim in data.get('identity_claims', []))):
        # The exact search-card/variant metadata can expose an MPN omitted
        # from the visible product name. The shared variant/brand vetoes above
        # still apply; requiring that code in the title would discard the link.
        return True
    title_key = re.sub(r"[^a-z0-9]", "", title.casefold())
    model_tokens = [token for token in model.split("-") if len(token) >= 3 or any(ch.isdigit() for ch in token)]
    numeric_tokens = [token for token in model_tokens if any(ch.isdigit() for ch in token)]
    # Exact model tokens are required where present; this rejects confidently
    # wrong model extractions while tolerating spacing and punctuation changes.
    if numeric_tokens and not all(token in title_key for token in numeric_tokens):
        return False
    if not numeric_tokens and not any(token in title_key for token in model_tokens):
        return False
    capacity_gb = (data.get("specs") or {}).get("capacity_gb")
    if capacity_gb is not None:
        try:
            expected = int(float(capacity_gb))
        except (ValueError, TypeError):
            return False
        capacities = re.findall(r"\b(\d+(?:\.\d+)?)\s*(tb|gb)\b", title.casefold())
        if capacities:
            title_capacities = {int(float(amount) * (1000 if unit == "tb" else 1)) for amount, unit in capacities}
            if expected not in title_capacities:
                return False
    return True


def _asin_for_listing(external_id: str, url: str | None) -> str | None:
    asin = extract_asin(url) or extract_asin(external_id)
    if asin:
        return asin
    match = re.fullmatch(r"amazon-(?:bestseller|requirement):([A-Z0-9]{10})", external_id, re.I)
    return match.group(1).upper() if match else None


async def reconcile_active_catalogue_cpks(db: AsyncSession, *, allow_model_extraction: bool = True) -> dict[str, int]:
    """ASIN-first identity enrichment for every selected Curated product.

    Active, pending-review and retained hidden products in the selected range
    are considered, so CPK/vendor matching is ready before a bestseller is
    approved for sale. ASIN CPKs must be unique and
    category-valid. Missing ASIN links fall back to deterministic identity
    resolution and a free-only extractor for specific unresolved products.
    Paid model tiers are never used.
    """
    products = (await db.execute(text("""
        SELECT DISTINCT ON (l.id)
               l.id AS listing_pk, l.external_id, l.url, l.title, l.price,
               MAX(l.raw_specs::text)::json AS raw_specs,
               array_agg(DISTINCT s.slot_type) AS roles,
               current.cpk AS current_cpk, current.cpk_data AS current_data,
               current.cpk_confidence AS current_confidence
        FROM catalogue_variants v
        JOIN playbook_slots s ON s.id = v.slot_id
        JOIN listings l ON l.id = v.listing_id
        LEFT JOIN gem_radar_listing_cpk current ON current.listing_id = l.external_id
        WHERE v.curated_for_builds IS TRUE
          AND v.status IN ('active','pending_review','hidden')
          AND l.status = 'active'
        GROUP BY l.id, l.external_id, l.url, l.title, l.price,
                 current.cpk, current.cpk_data, current.cpk_confidence
        ORDER BY l.id
    """))).mappings().all()
    asins = {
        asin for row in products
        if (asin := _asin_for_listing(row["external_id"], row["url"]))
    }
    asin_rows: dict[str, list[dict]] = {}
    bestseller_cpks: dict[str, list[str]] = {}
    if asins:
        rows = (await db.execute(text("""
            SELECT listing_id, cpk, cpk_data, cpk_confidence
            FROM gem_radar_listing_cpk
            WHERE listing_id = ANY(:asins)
        """), {"asins": list(asins)})).mappings().all()
        for row in rows:
            asin_rows.setdefault(row["listing_id"], []).append(dict(row))
        bestseller_rows = (await db.execute(text("""
            SELECT DISTINCT ON (asin) asin, cpk
            FROM amazon_bestseller_observations
            WHERE asin = ANY(:asins) AND cpk IS NOT NULL
            ORDER BY asin, captured_at DESC, id DESC
        """), {"asins": list(asins)})).mappings().all()
        for row in bestseller_rows:
            bestseller_cpks.setdefault(row["asin"], []).append(row["cpk"])
    cpk_metadata: dict[str, list[dict]] = {}
    candidate_keys = {cpk for values in bestseller_cpks.values() for cpk in values}
    if candidate_keys:
        rows = (await db.execute(text("""
            SELECT DISTINCT cpk, cpk_data, cpk_confidence
            FROM gem_radar_listing_cpk
            WHERE cpk = ANY(:cpks)
        """), {"cpks": list(candidate_keys)})).mappings().all()
        for row in rows:
            cpk_metadata.setdefault(row["cpk"], []).append(dict(row))

    # Reuse an existing vendor CPK only when a unique, specific model alias
    # occurs in the catalogue title. This helps listings whose ASIN source
    # has no identity and whose title needs no LLM extraction.
    known_rows = (await db.execute(text("""
        SELECT DISTINCT cpk, cpk_data
        FROM gem_radar_listing_cpk
        WHERE cpk IS NOT NULL AND cpk_data IS NOT NULL
    """))).mappings().all()
    aliases: list[tuple[str, str, dict]] = []
    for known in known_rows:
        data = known["cpk_data"] or {}
        if not data.get("category") or not data.get("brand") or not data.get("model"):
            continue
        for value in (data.get("model"), f"{data.get('brand') or ''}{data.get('model') or ''}"):
            alias = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
            if len(alias) >= 8:
                aliases.append((alias, known["cpk"], dict(data)))

    counts = {"active_products": len(products), "asin_matched": 0,
              "deterministic_matched": 0, "already_valid": 0,
              "free_llm_matched": 0, "free_llm_attempted": 0,
              "free_llm_skipped_recent": 0, "unresolved": 0, "updated": 0}
    writes: dict[str, tuple[str, dict, float]] = {}
    free_settings = get_settings()
    free_provider_available = allow_model_extraction and bool(free_settings.ollama_base_url or free_settings.openrouter_api_key)
    retry_after = timedelta(days=7)
    provider_retry_after = timedelta(hours=24)
    now = datetime.now(timezone.utc)
    resolution_markers: dict[int, dict] = {}
    free_extraction_candidates: dict[int, tuple[str, str, set[str], str]] = {}
    for row in products:
        external_id = row["external_id"]
        roles = set(row["roles"] or [])
        title = row["title"] or ""
        asin = _asin_for_listing(external_id, row["url"])

        # Use the same identifier registry as ingestion before any legacy
        # title/ASIN fallback. A conflict must never fall through to an alias.
        from app.gem_radar.product_identity_registry import resolve_identifiers
        raw = row["raw_specs"] or {}
        categories = {category for role in roles for category in _ROLE_CATEGORIES.get(role, set())}
        category = "ssd" if categories and categories <= {"ssd", "storage"} else (
            next(iter(categories)) if len(categories) == 1 else None)
        resolved = await resolve_identifiers(db, title=title, category=category,
            gtin=raw.get("gtin"), mpn=raw.get("mpn"), source_url=row["url"])
        if resolved:
            if resolved["status"] == "conflict":
                from app.gem_radar.cpk_market import remove_listing_price
                await remove_listing_price(db, external_id)
                if row["current_cpk"]:
                    data = {**(row["current_data"] or {}), "identity_status": "conflict",
                            "identity_conflict": resolved}
                    writes[external_id] = (row["current_cpk"], data, 0.0)
                counts["unresolved"] += 1
                continue
            data = {**resolved["data"], "identity_claims": resolved["claims"],
                    "catalogue_identity_match": "identifier_registry"}
            writes[external_id] = (resolved["cpk"], data, 1.0)
            counts["identifier_matched"] = counts.get("identifier_matched", 0) + 1
            continue

        # An exact ASIN CPK wins over a derived local identity, provided the
        # source CPK has one unambiguous, category-compatible identity.
        valid_asin = []
        for candidate in asin_rows.get(asin or "", []):
            data = candidate.get("cpk_data") or {}
            if candidate.get("cpk") and identity_is_usable(title, data, roles):
                valid_asin.append(candidate)
        for cpk in bestseller_cpks.get(asin or "", []):
            for candidate in cpk_metadata.get(cpk, []):
                data = candidate.get("cpk_data") or {}
                if identity_is_usable(title, data, roles):
                    valid_asin.append({**candidate, "cpk": cpk})
        asin_cpks = {candidate["cpk"] for candidate in valid_asin}
        chosen = None
        if len(asin_cpks) == 1:
            chosen = next(candidate for candidate in valid_asin if candidate["cpk"] in asin_cpks)
            data = dict(chosen["cpk_data"] or {})
            if (row["current_cpk"] == chosen["cpk"]
                    and identity_is_usable(title, row["current_data"] or {}, roles)):
                counts["asin_matched"] += 1
                counts["already_valid"] += 1
                continue
            data["cpk"] = chosen["cpk"]
            data["catalogue_identity_match"] = "exact_asin"
            writes[external_id] = (chosen["cpk"], data,
                                   float(chosen.get("cpk_confidence") or data.get("confidence") or 0.9))
            counts["asin_matched"] += 1
            continue

        current_data = row["current_data"] or {}
        if row["current_cpk"] and identity_is_usable(title, current_data, roles):
            if current_data.get("catalogue_identity_match") == "deterministic_title":
                identity = resolve_identity(title, delivered_price=row["price"])
                deterministic = _deterministic_identity(title, next(iter(roles), None), row["price"])
                if (float(identity.exact_sku_confidence or 0) >= 0.70 and deterministic is not None
                        and deterministic[0] != row["current_cpk"]
                        and identity_is_usable(title, deterministic[1], roles)):
                    data = dict(deterministic[1])
                    data["extraction_method"] = "catalogue_deterministic"
                    data["catalogue_identity_match"] = "deterministic_title"
                    writes[external_id] = (deterministic[0], data, float(data.get("confidence") or 0))
                    counts["deterministic_matched"] += 1
                    continue
            counts["already_valid"] += 1
            continue

        title_key = re.sub(r"[^A-Z0-9]", "", title.upper())
        alias_matches = [item for item in aliases
                         if item[0] in title_key
                         and identity_is_usable(title, item[2], roles)]
        if alias_matches:
            longest = max(len(item[0]) for item in alias_matches)
            best = [item for item in alias_matches if len(item[0]) == longest]
            candidate_cpks = {item[1] for item in best}
            if len(candidate_cpks) == 1:
                candidate = best[0]
                data = dict(candidate[2])
                data["cpk"] = candidate[1]
                data["catalogue_identity_match"] = "unique_model_alias"
                writes[external_id] = (candidate[1], data,
                                       float(data.get("confidence") or 0.9))
                counts["deterministic_matched"] += 1
                continue

        identity = resolve_identity(title, delivered_price=row["price"])
        confidence = float(identity.exact_sku_confidence or 0)
        deterministic = _deterministic_identity(title, next(iter(roles), None), row["price"])
        if (confidence >= 0.70 and deterministic is not None
                and identity_is_usable(title, deterministic[1], roles)):
            cpk, identity_data = deterministic
            identity_data = dict(identity_data)
            identity_data["extraction_method"] = "catalogue_deterministic"
            identity_data["catalogue_identity_match"] = "deterministic_title"
            writes[external_id] = (cpk, identity_data, confidence)
            counts["deterministic_matched"] += 1
        else:
            role_categories = {
                "cpu": "cpu", "gpu": "gpu", "motherboard": "motherboard",
                "ram": "ram", "storage": "ssd", "storage_secondary": "ssd",
                "psu": "psu", "cooling": "cooler", "case": "case",
            }
            allowed_categories = {role_categories[role] for role in roles if role in role_categories}
            marker = (row["raw_specs"] or {}).get("catalogue_cpk_resolution", {})
            attempted_at = marker.get("attempted_at")
            try:
                previous_attempt = datetime.fromisoformat(str(attempted_at).replace("Z", "+00:00"))
                if previous_attempt.tzinfo is None:
                    previous_attempt = previous_attempt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                previous_attempt = None
            category = next(iter(allowed_categories)) if len(allowed_categories) == 1 else None
            preflight_flags = identity_gates(title, {"category": category}) if category else ["ambiguous_catalogue_role"]
            extraction_allowed = (
                free_provider_available
                and category is not None
                and len(title.strip()) >= 12
                and not any(flag != "identity_incomplete" for flag in preflight_flags)
            )
            marker_retry_after = (
                provider_retry_after if marker.get("status") == "provider_unavailable" else retry_after
            )
            if extraction_allowed and previous_attempt and now - previous_attempt < marker_retry_after:
                counts["free_llm_skipped_recent"] += 1
                counts["unresolved"] += 1
            elif extraction_allowed:
                free_extraction_candidates[row["listing_pk"]] = (
                    external_id, title, roles, category
                )
            else:
                counts["unresolved"] += 1

    if free_extraction_candidates:
        candidates = list(free_extraction_candidates.items())
        for index, (listing_pk, (external_id, title, roles, category)) in enumerate(candidates):
            try:
                extracted = await extract_cpk(
                    title, category=category, condition="new", free_only=True,
                    local_only=True, raise_on_provider_error=True, timeout=90,
                )
            except Exception:
                # A free-provider outage must not fan out into dozens of
                # repeated timeouts/429s on each hourly catalogue refresh.
                for pending_id, _pending in candidates[index:]:
                    resolution_markers[pending_id] = {
                        "attempted_at": now.isoformat(),
                        "status": "provider_unavailable",
                        "provider_policy": "local_or_free_only",
                    }
                    counts["unresolved"] += 1
                counts["free_llm_attempted"] += 1
                counts["free_llm_provider_failed"] = 1
                counts["free_llm_skipped_provider"] = len(candidates) - index - 1
                break
            counts["free_llm_attempted"] += 1
            if extracted and identity_is_usable(title, extracted.to_dict(), roles):
                identity_data = extracted.to_dict()
                identity_data["extraction_method"] = "catalogue_free_llm"
                identity_data["catalogue_identity_match"] = "free_llm_title"
                writes[external_id] = (extracted.cpk, identity_data, extracted.confidence)
                counts["free_llm_matched"] += 1
            else:
                counts["unresolved"] += 1
                resolution_markers[listing_pk] = {
                    "attempted_at": now.isoformat(),
                    "status": "unresolved",
                    "provider_policy": "local_or_free_only",
                }

    for external_id, (cpk, data, confidence) in writes.items():
        await db.execute(text("""
            INSERT INTO gem_radar_listing_cpk
                (listing_id, cpk, cpk_data, cpk_confidence, updated_at)
            VALUES (:listing_id, :cpk, CAST(:cpk_data AS jsonb), :confidence, CURRENT_TIMESTAMP)
            ON CONFLICT (listing_id) DO UPDATE SET
                cpk = EXCLUDED.cpk,
                cpk_data = EXCLUDED.cpk_data,
                cpk_confidence = EXCLUDED.cpk_confidence,
                updated_at = CURRENT_TIMESTAMP
        """), {"listing_id": external_id, "cpk": cpk,
                "cpk_data": json.dumps(data), "confidence": confidence})
    product_by_id = {product["listing_pk"]: product for product in products}
    for listing_pk, marker in resolution_markers.items():
        row = product_by_id[listing_pk]
        raw_specs = dict(row["raw_specs"] or {})
        raw_specs["catalogue_cpk_resolution"] = marker
        await db.execute(text("""
            UPDATE listings SET raw_specs = CAST(:raw_specs AS json)
            WHERE id = :listing_pk
        """), {"listing_pk": listing_pk, "raw_specs": json.dumps(raw_specs)})
    counts["updated"] = len(writes)
    return counts
