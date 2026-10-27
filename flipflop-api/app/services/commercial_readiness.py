"""Read-only bootstrap/readiness from canonical cells and existing observations."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
import re
from types import SimpleNamespace

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

from app.models.catalogue import CatalogueVariant, CaseCatalogue, PlaybookSlot
from app.models.curated_build_segment import CuratedBuildSegment
from app.models.commerce_evidence import PriceQuoteSnapshot, SupplierOfferEvidence
from app.models.gem_radar_observation import GemRadarListingObservation
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.models.gem_radar_listing_lifecycle import GemRadarListingLifecycle
from app.models.listing import Listing
from app.models.listing_archive import ListingArchive
from app.models.playbook import Playbook, PlaybookProposal
from app.schemas.commercial_quote import CellCommercialPolicy
from app.services.commercial_checkout import current_capacity_ids
from app.services.commercial_quote_evidence import definition_hash, latest_listing_observations, assess_stored_cell, supplier_identity
from app.services.commerce_pricing import _recent
from app.services.curated_build_policy import definitions, matches_spec


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


def supplier_capture_fingerprint(data):
    """Fingerprint commercial listing facts without volatile scrape bookkeeping.

    Collection time and observation IDs are retained for display and freshness
    checks, but recapturing unchanged facts should not invalidate a review.
    """
    # Arrival ETA display fields can be enriched from saved vendor defaults
    # without changing the underlying listing evidence the operator reviewed.
    # Keep supplier identity, item price, stock, condition and postage in the
    # fingerprint, but do not invalidate review when those saved defaults are
    # added to an otherwise identical capture.
    volatile={'fingerprint','fresh','observed_at','observation_id','capture_refresh_warning',
        'delivery_estimate_source'}
    canonical=dict(data)
    # Legacy captures may omit the flag while newer ones explicitly store
    # false. Both mean the same thing for costing: use the approved £0 fallback.
    if canonical.get('postage_verified') is not True:
        canonical['postage_verified']=False
        canonical['delivery_gbp']='0.00'
        canonical['postage_assumption']='owner-approved-zero-fallback'
    if canonical.get('delivery_estimate_source') in {
            'vendor_default','prime_default','saved_vendor_default',
            'configured_vendor_default','owner_fallback'}:
        # A saved ETA default is policy, not a changed supplier capture. The
        # resulting build delivery quote remains revisioned separately.
        volatile.add('delivery_working_days')
    return fingerprint({key:value for key,value in canonical.items() if key not in volatile})


def _apply_unknown_supplier_postage_fallback(data):
    """Cost any unverified inbound delivery at £0 without claiming free shipping."""
    if data.get('postage_verified') is True:
        return
    data['delivery_gbp']='0.00'
    data['postage_assumption']='owner-approved-zero-fallback'


def price_review_hash(assessment):
    if not assessment:
        return None
    return fingerprint({'modes': {
        name: {field: offer.get(field) for field in ('offerable', 'price_gbp', 'delivery_working_days',
                                                    'supplier_offer_ids', 'capacity_evidence_id')}
        for name, offer in assessment['modes'].items()}})


def product_key(playbook_id, cell_id):
    return f"playbook:{playbook_id}:cell:{cell_id}"


def catalogue_required_roles(definition):
    """Use the Playbook assembler's role rules for readiness coverage."""
    # Imported lazily because playbook_service itself uses helpers from this
    # module. The call happens after both modules have finished loading.
    from app.services.playbook_service import required_parts
    return set(required_parts(definition))


def catalogue_selected_roles(proposal, required_roles):
    """Return roles with concrete IDs in the service-generated proposal BOM."""
    data = getattr(proposal, "proposed_data", None) or {}
    selected = set()
    for part in data.get("components", []):
        if (part.get("role") in required_roles
                and (part.get("variant_id") or part.get("case_catalogue_id"))):
            selected.add(part["role"])
    return selected


async def cell_context(db, playbook_id, cell_id, *, lock=False):
    query = select(Playbook).where(Playbook.id == playbook_id, Playbook.status == "active")
    if lock:
        query = query.with_for_update()
    parent = (await db.execute(query)).scalar_one_or_none()
    definition = next((item for item in definitions()["builds"] if item["id"] == cell_id), None)
    if parent is None or definition is None or parent.name != definition["segment"]:
        raise HTTPException(404, "Active Playbook cell not found")
    return parent, definition


async def latest_draft(db, playbook_id, cell_id):
    return (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.product_key == product_key(playbook_id, cell_id),
        PriceQuoteSnapshot.status == "policy_draft",
    ).order_by(PriceQuoteSnapshot.id.desc()).limit(1))).scalar_one_or_none()


def policy_errors(raw):
    try:
        return CellCommercialPolicy.model_validate(normalize_catalogue_policy(raw)), []
    except ValidationError as error:
        return None, [{"field": ".".join(str(item) for item in entry["loc"]), "message": entry["msg"]}
                      for entry in error.errors(include_input=False, include_context=False, include_url=False)]


def draft_errors(raw):
    policy, errors = policy_errors(raw)
    mapping = raw.get("checkout_slot_parts") or {}
    case = raw.get("checkout_case")
    if not mapping:
        errors.append({"field": "checkout_slot_parts", "message": "Reviewed component mappings are required"})
    if not case:
        errors.append({"field": "checkout_case", "message": "Select a reviewed case"})
    mapped = {value[1] for value in mapping.values() if isinstance(value, (list, tuple)) and len(value) == 2}
    if isinstance(case, (list, tuple)) and len(case) == 2:
        mapped.add(case[1])
    if mapped != set(raw.get("required_part_keys") or []):
        errors.append({"field": "required_part_keys", "message": "Required products must exactly match reviewed components and case"})
    return policy, errors


def normalize_catalogue_policy(raw):
    """An unused comparable-market check must not demand invented sold prices."""
    if not isinstance(raw, dict):
        return raw
    normalized = dict(raw)
    market = normalized.get("market")
    if isinstance(market, dict) and not any(market.get(key) is not None and market.get(key) != ''
        for key in ('sold_median_gbp', 'sold_p75_gbp', 'sold_sample_size', 'minimum_sold_sample_size',
                    'cap_method', 'observed_at', 'evidence_source', 'evidence_ref')):
        normalized['market'] = None
        normalized['market_tolerance_fraction'] = '0'
    elif isinstance(market, dict) and market.get('sold_median_gbp') is None:
        normalized['market'] = None
        normalized['market_tolerance_fraction'] = '0'
    return normalized


async def readiness_index(db):
    parents = {row.name: row for row in (await db.execute(select(Playbook).where(Playbook.status == "active"))).scalars().all()}
    drafts = (await db.execute(select(PriceQuoteSnapshot).where(
        PriceQuoteSnapshot.status == "policy_draft",
    ).order_by(PriceQuoteSnapshot.id.desc()))).scalars().all()
    draft_by_key = {}
    for row in drafts:
        draft_by_key.setdefault(row.product_key, row.evidence_json.get("draft") or {})
    draft_keys = set(draft_by_key)
    cells = definitions()["builds"]
    proposals = (await db.execute(select(PlaybookProposal).where(
        PlaybookProposal.action == "UPDATE", PlaybookProposal.status.in_(("pending", "approved")),
    ).order_by(PlaybookProposal.id.desc()))).scalars().all()
    proposal_by_cell = {}
    for proposal in proposals:
        if (proposal.demand_signals or {}).get("source") != "catalogue_playbook_service_v1":
            continue
        cell_id = (proposal.proposed_data or {}).get("cell_id")
        if cell_id:
            proposal_by_cell.setdefault((proposal.playbook_id, cell_id), proposal)
    required = set()
    for parent in parents.values():
        for raw in ((parent.pricing_model or {}).get("commercial_cells") or {}).values():
            if isinstance(raw, dict):
                required.update(raw.get("required_part_keys") or [])
    for candidate in draft_by_key.values():
        required.update(candidate.get("required_part_keys") or [])
    rows = (await db.execute(select(SupplierOfferEvidence).where(
        SupplierOfferEvidence.part_key.in_(required),
        SupplierOfferEvidence.observed_at >= datetime.now(timezone.utc) - timedelta(hours=24),
    ))).scalars().all() if required else []
    fresh = latest_listing_observations(rows)
    capacities = await current_capacity_ids(db)
    now = datetime.now(timezone.utc)
    items = []
    for definition in cells:
        parent = parents.get(definition["segment"])
        raw = (((parent.pricing_model or {}).get("commercial_cells") or {}).get(definition["id"])) if parent else None
        policy, errors = policy_errors(raw) if raw else (None, [])
        blockers = []
        required_roles = catalogue_required_roles(definition)
        proposal = proposal_by_cell.get((parent.id, definition['id'])) if parent else None
        selected_roles = catalogue_selected_roles(proposal, required_roles)
        missing_roles = required_roles - selected_roles
        candidate = draft_by_key.get(product_key(parent.id, definition["id"]), {}) if parent else {}
        coverage_keys = set(policy.required_part_keys if policy else candidate.get("required_part_keys") or [])
        coverage_condition = policy.condition.value if policy else candidate.get("condition", "new")
        covered = {row.part_key for row in fresh if row.stock_confirmed and row.condition == coverage_condition
                   and row.delivery_working_days is not None and row.delivery_working_days >= 0
                   and row.supplier_confidence >= Decimal("0.8")
                   and _recent(row.observed_at.isoformat(), now, timedelta(hours=24))}
        if not parent:
            blockers.append("No active parent Playbook")
        elif missing_roles:
            blockers.append('Playbook sourcing needs catalogue products: ' + ', '.join(sorted(missing_roles)))
        elif raw is None:
            blockers.append("Calculate and review selling prices")
        elif not policy:
            blockers.append("Approved policy needs correction")
        if policy:
            if policy.definition_sha256 != definition_hash(definition):
                blockers.append("Build definition changed since review")
            missing = set(policy.required_part_keys) - covered
            if missing:
                blockers.append(f"{len(missing)} products need current supplier evidence")
            if policy.market is not None and not _recent(policy.market.observed_at, now, timedelta(days=30)):
                blockers.append("Sold-market comparison is stale")
        if not capacities and not missing_roles:
            blockers.append("Current workshop evidence is missing or full")
        items.append({"cell_id": definition["id"], "name": definition["name"],
            "segment": definition["segment"], "tier": definition["tier"],
            "playbook_id": parent.id if parent else None, "policy_version": policy.version if policy else None,
            "checkout_enabled": bool(policy and policy.checkout_enabled),
            "has_draft": bool(parent and product_key(parent.id, definition["id"]) in draft_keys),
            "required_products": len(coverage_keys) if coverage_keys else None,
            "catalogue_selected_products": len(selected_roles), "catalogue_required_products": len(required_roles),
            "evidenced_products": len(covered & coverage_keys),
            "state": "needs_setup" if not policy else "needs_evidence" if blockers else "ready_for_assessment",
            "blockers": blockers, "policy_errors": errors})
    return {"items": items, "observed_at": now.isoformat(),
            "note": "Ready for assessment does not mean approved or enabled for sale."}


def _captured_url_belongs_to_listing(captured_url, listing, observation):
    """Bind an exact OCU product page to its matching catalogue SKU.

    Some OCU catalogue records retain a search URL while the collector has a
    product-page capture. Accept that capture only when the external SKU and
    normalized product title both match the exact observation.
    """
    if not captured_url:
        return False
    if same_listing_product(captured_url, listing.url):
        return True
    from urllib.parse import urlsplit
    from app.services.playbook_product_capture import supported_product_url
    try:
        parsed=urlsplit(captured_url)
    except ValueError:
        return False
    if (observation is None or observation.source!='overclockers'
            or supplier_identity(observation.source,'')!=supplier_identity(listing.source_name,listing.url)
            or not supported_product_url(captured_url)):
        return False
    sku=re.search(r'/([A-Z0-9-]+)\.html$',parsed.path,re.I)
    external_id=str(listing.external_id or '')
    normalize=lambda value: re.sub(r'[^a-z0-9]','',str(value or '').casefold())
    return bool(sku and external_id.casefold()==sku.group(1).casefold()
        and str(observation.listing_id).casefold()==external_id.casefold()
        and normalize(listing.title)==normalize(observation.title))


def observation_data(listing, observation, score, lifecycle):
    if observation is None:
        return None
    active = listing.status == "active" and observation.listing_type == "buy_it_now"
    if lifecycle and lifecycle.status != "active":
        archived = lifecycle.archived_at
        active = active and archived is not None and utc(observation.observed_at) > utc(archived)
    capture = observation.commercial_source_evidence or {}
    stock_status = capture.get("stock_status", "unknown")
    stock_evidence = capture.get("stock_evidence")
    # Prefer explicit stock phrases from the same captured product, then
    # apply the owner's default for a current listing with no negative signal.
    from app.services.playbook_product_capture import supported_product_url
    if (stock_status == "unknown" and observation.source in {"amazon", "overclockers"}
            and capture.get("url") and supported_product_url(capture.get("url"))
            and _captured_url_belongs_to_listing(capture.get("url"), listing, observation)
            and capture.get("observed_at")):
        stock_status, stock_evidence = _retailer_stock_from_text(
            getattr(observation, "delivery_text", None))
    from app.services.commercial_source import search_listing_availability
    stock_status, stock_evidence, availability_assumed = search_listing_availability(
        stock_status, stock_evidence, listing_type=observation.listing_type, active=active)
    delivery_days=observation.delivery_working_days
    delivery_source=observation.delivery_estimate_source
    if delivery_days is None:
        from app.services.commerce_pricing import estimate_delivery_working_days
        delivery_days,delivery_source=estimate_delivery_working_days(
            str(observation.source or 'retail'),None,observation.prime_eligible)
    data = {"listing_db_id": listing.id, "listing_id": observation.listing_id,
        "observation_id": observation.id, "observed_at": capture.get("observed_at") or utc(observation.observed_at).isoformat(),
        "url": capture.get('url') if _captured_url_belongs_to_listing(capture.get('url'), listing, observation) else listing.url,
        "source": observation.source,
        "condition": observation.condition_normalised, "listing_type": observation.listing_type,
        "item_gbp": capture.get("item_gbp", str(observation.item_price)), "delivery_gbp": capture.get("delivery_gbp", str(observation.postage_price)),
        "stock_status": stock_status,
        "stock_evidence": stock_evidence,
        "availability_assumed": availability_assumed,
        "commercial_capture_verified": bool(capture.get("observed_at")
            and _captured_url_belongs_to_listing(capture.get('url'),listing,observation)),
        "delivery_working_days": delivery_days,
        "delivery_estimate_source": delivery_source,
        "prime_eligible": observation.prime_eligible, "active_listing": active,
        "lifecycle_status": lifecycle.status if lifecycle else None,
        "lifecycle_updated_at": utc(lifecycle.updated_at).isoformat() if lifecycle else None,
        "identity_source": "approved_catalogue_listing_link",
        "cpk": score.cpk if score else None}
    # Source fields may contain either a saved vendor default or a captured
    # destination-specific estimate. Neither proves that an amount of £0 means
    # free postage. Only explicit delivery text or a collector's verified
    # postage flag can establish postage evidence.
    import re
    delivery_text=str(getattr(observation,'delivery_text',None) or '')
    explicit_free=bool(re.search(r'\bfree\s+(?:delivery|shipping)\b',delivery_text,re.I)) and not bool(
        re.search(r'\b(?:orders? over|minimum|eligible|prime members?|subscription)\b',delivery_text,re.I))
    amount=data.get('delivery_gbp')
    try:
        paid=Decimal(str(amount)) if amount is not None else None
        explicit_paid=paid is not None and paid.is_finite() and paid>0
    except Exception:
        explicit_paid=False
    data['postage_verified']=bool(capture.get('postage_verified') is True or explicit_free or explicit_paid)
    _apply_unknown_supplier_postage_fallback(data)
    data["fingerprint"] = supplier_capture_fingerprint(data)
    data["fresh"] = _recent(data["observed_at"], datetime.now(timezone.utc), timedelta(hours=24))
    return data


def _retailer_stock_from_text(value):
    """Return stock only for unambiguous retailer wording in the captured card."""
    import re
    text = str(value or "")
    if re.search(r"\b(?:currently unavailable|out of stock|temporarily out of stock|sold out)\b", text, re.I):
        return "unavailable", text[:1000]
    if re.search(r"\bonly\s+\d+\s+left\s+in\s+stock\b|\bin stock\b|\bavailable to ship\b", text, re.I):
        return "available", text[:1000]
    return "unknown", None


async def source_preview(db, listing):
    free_software=(listing.raw_specs or {}).get('playbook_free_software') if isinstance(listing.raw_specs,dict) else None
    if isinstance(free_software,dict) and free_software.get('kind')=='official_free_os_download':
        return official_free_software_preview(listing,free_software)
    # Exact persisted URL binds the collector's external ID to the reviewed
    # catalogue Listing. A title-only match never qualifies.
    if not listing.url or not listing.url.strip():
        return None
    score = (await db.execute(select(GemRadarScoredListing).where(
        GemRadarScoredListing.url == listing.url,
    ).order_by(GemRadarScoredListing.scored_at.desc(), GemRadarScoredListing.id.desc()).limit(1))).scalar_one_or_none()
    external_id = str((score.listing_id if score else listing.external_id) or "")
    if external_id.startswith('amazon-bestseller:'):
        external_id = external_id.split(':',1)[1]
    if not external_id:
        return await _product_page_source_preview(db, listing)
    if external_id.startswith("ebay_v1|"):
        external_id = external_id.split("|")[1]
    observation = (await db.execute(select(GemRadarListingObservation).where(
        GemRadarListingObservation.listing_id == external_id,
    ).order_by(GemRadarListingObservation.observed_at.desc(), GemRadarListingObservation.id.desc()).limit(1))).scalar_one_or_none()
    lifecycle = await db.get(GemRadarListingLifecycle, external_id)
    capture = observation.commercial_source_evidence if observation else None
    if capture and not _captured_url_belongs_to_listing(capture.get("url"), listing, observation):
        return None
    if observation and supplier_identity(observation.source, "") != supplier_identity(listing.source_name, listing.url):
        return None
    data = observation_data(listing, observation, score, lifecycle)
    if data and capture and _captured_url_belongs_to_listing(capture.get('url'),listing,observation):
        data['commercial_capture_verified'] = bool(capture.get('observed_at'))
        data['fingerprint'] = supplier_capture_fingerprint(data)
    if data:
        archived = (await db.execute(select(ListingArchive.id).where(
            ListingArchive.external_id.in_({external_id, listing.external_id}),
        ).limit(1))).scalar_one_or_none()
        if archived:
            data["active_listing"] = False
            data["archive_id"] = archived
            data["fingerprint"] = supplier_capture_fingerprint(data)
    product_page = await _product_page_source_preview(db, listing)
    if prefer_exact_product_page_preview(product_page,data):
        return product_page
    return data or product_page


async def source_preview_many(db, listings):
    """Resolve exact source previews for a catalogue batch with bounded queries."""
    listings = list(listings)
    if not listings:
        return {}
    result = {listing.id: None for listing in listings if not listing.url or not listing.url.strip()}
    listings = [listing for listing in listings if listing.url and listing.url.strip()]
    if not listings:
        return result
    for listing in listings:
        raw = listing.raw_specs if isinstance(listing.raw_specs, dict) else {}
        free_software = raw.get('playbook_free_software')
        if isinstance(free_software, dict) and free_software.get('kind') == 'official_free_os_download':
            result[listing.id] = official_free_software_preview(listing, free_software)

    urls = {listing.url for listing in listings}
    score_rows = (await db.execute(select(GemRadarScoredListing).where(
        GemRadarScoredListing.url.in_(urls),
    ).order_by(GemRadarScoredListing.url, GemRadarScoredListing.scored_at.desc(),
               GemRadarScoredListing.id.desc()))).scalars().all()
    scores = {}
    for score in score_rows:
        scores.setdefault(score.url, score)

    external_ids = {}
    original_ids = set()
    for listing in listings:
        if listing.id in result:
            continue
        score = scores.get(listing.url)
        external_id = str((score.listing_id if score else listing.external_id) or '')
        if external_id.startswith('amazon-bestseller:'):
            external_id = external_id.split(':', 1)[1]
        if external_id.startswith('ebay_v1|'):
            external_id = external_id.split('|', 1)[1]
        external_ids[listing.id] = external_id
        if external_id:
            original_ids.add(external_id)
        if listing.external_id:
            original_ids.add(str(listing.external_id))

    observations = {}
    lifecycles = {}
    archived_ids = {}
    ids = set(external_ids.values()) - {''}
    if ids:
        rows = (await db.execute(select(GemRadarListingObservation).where(
            GemRadarListingObservation.listing_id.in_(ids),
        ).order_by(GemRadarListingObservation.listing_id,
                   GemRadarListingObservation.observed_at.desc(),
                   GemRadarListingObservation.id.desc()))).scalars().all()
        for observation in rows:
            observations.setdefault(observation.listing_id, observation)
        lifecycles = {row.listing_id: row for row in (await db.execute(
            select(GemRadarListingLifecycle).where(GemRadarListingLifecycle.listing_id.in_(ids))
        )).scalars().all()}
    if original_ids:
        archived_rows = (await db.execute(select(ListingArchive.id, ListingArchive.external_id).where(
            ListingArchive.external_id.in_(original_ids),
        ))).all()
        archived_ids = {external_id: archive_id for archive_id, external_id in archived_rows}

    for listing in listings:
        if listing.id in result:
            continue
        score = scores.get(listing.url)
        external_id = external_ids.get(listing.id, '')
        observation = observations.get(external_id)
        lifecycle = lifecycles.get(external_id)
        data = None
        capture = observation.commercial_source_evidence if observation else None
        if capture and not _captured_url_belongs_to_listing(capture.get('url'), listing, observation):
            result[listing.id] = None
            continue
        if observation and supplier_identity(observation.source, '') != supplier_identity(
                listing.source_name, listing.url):
            result[listing.id] = None
            continue
        data = observation_data(listing, observation, score, lifecycle)
        if data and capture and _captured_url_belongs_to_listing(capture.get('url'), listing, observation):
            data['commercial_capture_verified'] = bool(capture.get('observed_at'))
            data['fingerprint'] = supplier_capture_fingerprint(data)
        archive_id = archived_ids.get(external_id) or archived_ids.get(str(listing.external_id or ''))
        if data and archive_id:
            data['active_listing'] = False
            data['archive_id'] = archive_id
            data['fingerprint'] = supplier_capture_fingerprint(data)
        product_page = await _product_page_source_preview(
            db, listing, archived=bool(archived_ids.get(str(listing.external_id or ''))))
        if prefer_exact_product_page_preview(product_page,data):
            result[listing.id] = product_page
        else:
            result[listing.id] = data or product_page
    return result


def prefer_exact_product_page_preview(product_page, listing_preview):
    """Prefer a same-price exact offer over a newer listing estimate with weaker facts."""
    if product_page is None:
        return False
    if listing_preview is None:
        return True
    try:
        page_time=utc(datetime.fromisoformat(product_page['observed_at']))
        listing_time=utc(datetime.fromisoformat(listing_preview['observed_at']))
    except (KeyError,TypeError,ValueError):
        return False
    if (product_page.get('identity_source')=='exact_retailer_product_page'
            and same_listing_product(product_page.get('url'),listing_preview.get('url'))):
        # A retained exact-page capture must not hide a newer verified offer
        # for the same listing. The approval endpoint rechecks the freshest
        # source, so pricing/rebuild and review must apply the same precedence.
        if (page_time < listing_time
                and listing_preview.get('commercial_capture_verified') is True
                and listing_preview.get('stock_status') == 'available'):
            return False
        if listing_preview.get('stock_status')=='unavailable' and listing_time>page_time:
            return False
        if (product_page.get('fresh') and listing_preview.get('identity_source') == 'approved_catalogue_listing_link'):
            # Ranking/search-card prices are not exact selected-offer quotes.
            # Prefer the complete fresh capture even if a newer card price differs.
            return True

        try:
            same_price=(Decimal(str(product_page.get('item_gbp')))
                ==Decimal(str(listing_preview.get('item_gbp'))))
        except Exception:
            same_price=False
        if same_price and product_page.get('condition')==listing_preview.get('condition'):
            def quality(source):
                score=0
                if source.get('stock_status')=='available' and source.get('stock_evidence'):
                    score+=1
                if source.get('postage_verified') is True:
                    score+=1
                if (isinstance(source.get('delivery_working_days'),int)
                        and not isinstance(source.get('delivery_working_days'),bool)
                        and source.get('delivery_working_days')>=0
                        and source.get('delivery_estimate_source')!='listing_estimate'):
                    score+=1
                if source.get('identity_source')=='exact_retailer_product_page':
                    score+=1
                return score
            if quality(product_page)>quality(listing_preview):
                return True
    return page_time>listing_time


def official_free_software_preview(listing, source):
    """Evidence for a zero-cost official download; this is not physical stock."""
    from urllib.parse import urlsplit
    url=str(listing.url or '')
    try:
        parsed=urlsplit(url)
        download=urlsplit(str(source.get('download_url') or ''))
        host=(parsed.hostname or '').casefold()
        download_host=(download.hostname or '').casefold()
    except ValueError:
        return None
    if (parsed.scheme!='https' or parsed.username or parsed.password
            or host!='releases.ubuntu.com' or download.scheme!='https'
            or download.username or download.password or download_host!='releases.ubuntu.com'
            or source.get('distribution')!='Ubuntu'
            or not re.fullmatch(r'\d{2}\.\d{2}',str(source.get('authored_release') or ''))
            or not re.search(rf'/ubuntu-{re.escape(str(source.get("authored_release")))}(?:\.\d+)*-desktop-amd64\.iso$',download.path,re.I)
            or source.get('available') is not True or Decimal(str(listing.price))!=Decimal('0')):
        return None
    observed=source.get('observed_at')
    try:
        timestamp=datetime.fromisoformat(str(observed).replace('Z','+00:00'))
    except ValueError:
        return None
    data={'listing_db_id':listing.id,'listing_id':str(listing.external_id or listing.id),
        'observation_id':listing.id,'observed_at':timestamp.isoformat(),'url':url,
        'source':'Ubuntu','condition':'new','listing_type':'software_download',
        'item_gbp':'0.00','delivery_gbp':'0.00','stock_status':'available',
        'stock_evidence':'Official Ubuntu desktop ISO link found on the release index; no physical stock.',
        'commercial_capture_verified':True,'product_properties':{'release':source['authored_release'],
            'download_url':source['download_url'],'licence_cost_gbp':'0.00'},'delivery_working_days':0,
        'delivery_estimate_source':'official_software_download','delivery_destination':None,
        'capture_refresh_warning':None,'prime_eligible':None,'active_listing':listing.status=='active',
        'lifecycle_status':None,'lifecycle_updated_at':None,'identity_source':'official_free_software',
        'postage_verified':True,'evidence_kind':'official_free_software',
        'fresh':_recent(timestamp.isoformat(),datetime.now(timezone.utc),timedelta(hours=24))}
    data['fingerprint']=supplier_capture_fingerprint(data)
    return data


async def _product_page_source_preview(db, listing, archived=None):
    """Expose a fresh, identity-bound retailer capture through the same review contract."""
    from urllib.parse import urlsplit
    capture = (listing.raw_specs or {}).get('playbook_product_capture') or {}
    if capture.get('status') != 'captured' or not listing.url or not same_listing_product(capture.get('url'), listing.url):
        return None
    try:
        observed = datetime.fromisoformat(capture['observed_at'])
        item = Decimal(str(capture['item_gbp']))
        postage = Decimal(str(capture['delivery_gbp'])) if capture.get('delivery_gbp') is not None else None
        delivery_days = capture.get('delivery_working_days')
        if (observed.tzinfo is None or observed > datetime.now(timezone.utc) or not item.is_finite()
                or item <= 0 or (postage is not None and (not postage.is_finite() or postage < 0))
                or (delivery_days is not None and (not isinstance(delivery_days, int)
                    or isinstance(delivery_days, bool) or delivery_days < 0))):
            return None
        from app.services.playbook_product_capture import supported_product_url
        if not supported_product_url(listing.url):
            return None
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return None
    if archived is None and listing.external_id:
        archived = (await db.execute(select(ListingArchive.id).where(
            ListingArchive.external_id == listing.external_id,
        ).limit(1))).scalar_one_or_none()
    stock = capture.get('stock_status')
    last_attempt = capture.get('last_capture_attempt') or {}
    # A retained price cannot overrule a newer explicit unavailable observation.
    if last_attempt.get('stock_status') == 'unavailable' or str(last_attempt.get('reason') or '').startswith('The exact Amazon ASIN is currently unavailable;'):
        stock = 'unavailable'

    active = listing.status == 'active' and not archived and stock == 'available'
    host = (urlsplit(listing.url).hostname or '').lower()
    source_name = listing.source_name or ('Amazon UK' if host.endswith('amazon.co.uk') else 'Overclockers UK')
    prime_eligible = capture.get('prime_eligible') if isinstance(capture.get('prime_eligible'), bool) else None
    delivery_days = capture.get('delivery_working_days')
    delivery_source = capture.get('delivery_estimate_source')
    if capture.get('digital_product') is True and host in {'gamers-outlet.net','www.gamers-outlet.net','royalcdkeys.com'}:
        delivery_days,delivery_source=0,'digital_delivery'
    if delivery_days is None:
        # Exact listing-level fallback: a visibly Prime-marked offer gets the
        # Prime default; other Amazon pages retain the configured vendor default.
        from app.services.commerce_pricing import estimate_delivery_working_days
        delivery_days, delivery_source = estimate_delivery_working_days(
            'Amazon UK' if host.endswith('amazon.co.uk') else source_name,
            None, prime_eligible)
    from app.services.commercial_source import search_listing_availability
    stock, stock_evidence, availability_assumed = search_listing_availability(
        stock, capture.get('stock_evidence'), active=active)
    data = {
        'listing_db_id': listing.id, 'listing_id': str(listing.external_id or listing.id),
        # Listing IDs are local provenance keys here; commercial evidence is
        # only written after an operator reviews and approves this proposal.
        'observation_id': listing.id, 'observed_at': observed.isoformat(), 'url': listing.url,
        'source': capture.get('merchant_name') or source_name,
        'condition': capture.get('condition') if capture.get('condition') in {'new','used','refurbished'} else 'unknown',
        'listing_type': 'buy_it_now',
        'item_gbp': str(item), 'delivery_gbp': str(postage) if postage is not None else None,
        'stock_status': stock if stock in {'available', 'unavailable'} else 'unknown',
        'stock_evidence': stock_evidence, 'availability_assumed': availability_assumed, 'commercial_capture_verified': True,
        'product_properties': capture.get('product_properties') if isinstance(capture.get('product_properties'),dict) else {},
        'delivery_working_days': delivery_days, 'delivery_estimate_source': delivery_source,
        'delivery_destination': capture.get('delivery_destination'),
        'capture_refresh_warning': (capture.get('last_capture_attempt') or {}).get('reason'),
        'prime_eligible': prime_eligible, 'active_listing': active, 'lifecycle_status': None,
        'lifecycle_updated_at': None, 'identity_source': 'exact_retailer_product_page',
        'postage_verified': capture.get('postage_verified') is True,
    }
    _apply_unknown_supplier_postage_fallback(data)
    data['fingerprint'] = supplier_capture_fingerprint(data)
    data['fresh'] = _recent(data['observed_at'], datetime.now(timezone.utc), timedelta(hours=24))
    review=(listing.raw_specs or {}).get('playbook_licence_source_review') or {}
    data['licence_review_fingerprint']=capture.get('licence_review_fingerprint')
    data['licence_source_reviewed']=bool(review.get('reviewed') is True
        and review.get('licence_review_fingerprint')==capture.get('licence_review_fingerprint'))
    data['licence_source_reviewed_at']=review.get('reviewed_at') if data['licence_source_reviewed'] else None
    return data


def same_listing_product(left, right):
    """Amazon tracking paths may differ; the exact ASIN must be identical."""
    if left == right:
        return True
    import re
    from urllib.parse import urlsplit
    try:
        urls=[urlsplit(value or '') for value in (left,right)]
    except ValueError:
        return False
    if any(url.scheme!='https' or not ((url.hostname or '')=='amazon.co.uk'
        or (url.hostname or '').endswith('.amazon.co.uk')) or url.username or url.password for url in urls):
        return False
    ids=[re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)',url.path,re.I) for url in urls]
    return bool(all(ids) and ids[0].group(1).upper()==ids[1].group(1).upper())


def empty_draft(definition, version, mappings, case_mapping):
    from app.services.commercial_pilot_policy import apply_pilot_rules
    costs = {key: None for key in ("build_labour", "packaging", "outbound_delivery", "insurance", "payment_fixed",
                                   "expected_failure_cost", "allocated_overhead", "other_variable_costs")}
    modes = {name: {"costs": dict(costs), "minimum_contribution_gbp": None, "minimum_margin_fraction": None,
        "premium_gbp": None, "workshop_working_days": None, "courier_working_days": None,
        "maximum_delivery_working_days": None} for name in ("fast_track", "standard", "flexible")}
    return apply_pilot_rules({"version": version, "definition_sha256": definition_hash(definition), "condition": "new",
        "required_part_keys": [part for _, part in mappings.values()] + ([case_mapping[1]] if case_mapping else []),
        "checkout_slot_parts": mappings, "checkout_case": case_mapping, "checkout_enabled": False,
        "vat_rate": None, "payment_rate": None, "warranty_rate": None, "returns_rate": None,
        "market_tolerance_fraction": None, "modes": modes,
        "market": {"condition": "new", "sold_median_gbp": None, "sold_p75_gbp": None,
                   "sold_sample_size": None, "minimum_sold_sample_size": None, "cap_method": None,
                   "observed_at": None, "evidence_source": None, "evidence_ref": None}}, definition.get("tier"))


async def readiness_detail(db, playbook_id, cell_id, case_id=None, reset_draft=False):
    parent, definition = await cell_context(db, playbook_id, cell_id)
    raw = ((parent.pricing_model or {}).get("commercial_cells") or {}).get(cell_id)
    policy, _ = policy_errors(raw) if raw else (None, [])
    saved = await latest_draft(db, playbook_id, cell_id)
    if case_id is None and saved and not reset_draft:
        candidate = (saved.evidence_json.get("draft") or {}).get("checkout_case")
        case_id = candidate[0] if isinstance(candidate, (list, tuple)) and candidate else None
    case_id = case_id or (policy.checkout_case[0] if policy and policy.checkout_case else None)
    cases = (await db.execute(select(CaseCatalogue).where(CaseCatalogue.status == "active").order_by(CaseCatalogue.name))).scalars().all()
    if case_id is not None and case_id not in {row.id for row in cases}:
        raise HTTPException(409, "Select an active case")
    parts, mappings = [], {}
    segment = (await db.execute(select(CuratedBuildSegment).where(
        CuratedBuildSegment.customer_type == definition["segment"],
        CuratedBuildSegment.budget_level == definition["tier"],
    ))).scalar_one_or_none()
    selected = (segment.components or {}) if segment else {}
    slot_rows = (await db.execute(select(PlaybookSlot).where(
        PlaybookSlot.playbook_id == playbook_id,
    ))).scalars().all()
    by_role = {slot.slot_type: slot for slot in slot_rows}
    required = list(dict.fromkeys([*definition.get("components", {}), "cpu", "motherboard", "ram", "storage", "cooling", "psu", "case"]))
    selected_case_listing = None
    for role in required:
        slot = by_role.get(role)
        variant_id = selected.get(role)
        variant = await db.get(CatalogueVariant, variant_id) if variant_id else None
        listing = await db.get(Listing, variant.listing_id) if variant else None
        if variant and (not slot or variant.slot_id != slot.id):
            variant, listing = None, None
        if role == "case":
            selected_case_listing = listing
            continue
        old = policy.checkout_slot_parts.get(slot.id) if policy and slot else None
        key = old[1] if old and variant and old[0] == variant.id else f"variant:{variant.id}" if variant else None
        if variant and key:
            mappings[slot.id] = [variant.id, key]
        parts.append(await catalogue_part(db, role, slot.id if slot else None, variant, listing, key,
                                          definition.get("components", {}).get(role)))
    if case_id is None and selected_case_listing:
        matching = [case for case in cases if case.id == selected_case_listing.case_catalogue_id
                    or matches_spec(case.name, selected_case_listing.title)]
        if len(matching) == 1:
            case_id = matching[0].id
    case_mapping = None
    case = next((row for row in cases if row.id == case_id), None)
    if case:
        key = policy.checkout_case[1] if policy and policy.checkout_case and policy.checkout_case[0] == case_id else f"case:{case_id}"
        case_mapping = [case_id, key]
        listing = selected_case_listing if selected_case_listing and (selected_case_listing.case_catalogue_id == case.id
            or matches_spec(case.name, selected_case_listing.title)) else None
        if listing is None:
            listing = (await db.execute(select(Listing).where(Listing.case_catalogue_id == case_id,
                Listing.status == "active").order_by(Listing.last_seen_at.desc(), Listing.id.desc()).limit(1))).scalar_one_or_none()
        part = await catalogue_part(db, "case", None, None, listing, key, definition.get("components", {}).get("case"))
        part.update(case_id=case.id, title=f"{case.brand} {case.name}")
        parts.append(part)
    else:
        parts.append(await catalogue_part(db, "case", None, None, selected_case_listing, None,
                                          definition.get("components", {}).get("case")))
    missing = [part["role"] for part in parts if not part["part_key"]]
    catalogue_error = None
    catalogue_blockers = (["Choose catalogue products for: " + ", ".join(missing)] if missing else [])
    inactive = [part['role'] for part in parts if part.get('variant_id') and part.get('catalogue_status') != 'active']
    if inactive:
        catalogue_blockers.append('Review or replace inactive catalogue products: ' + ', '.join(inactive))
    if selected_case_listing and not case_mapping:
        catalogue_blockers.append("Link the selected case to its case-catalogue product")
    candidate = saved.evidence_json["draft"] if saved and not reset_draft and case_id == (saved.evidence_json["draft"].get("checkout_case") or [None])[0] else raw
    draft = dict(candidate) if candidate else empty_draft(definition, (policy.version if policy else 0) + 1, mappings, case_mapping)
    draft["checkout_enabled"] = False
    if draft.get("market") is None:
        draft["market"] = {"condition": "new", "sold_median_gbp": None, "sold_p75_gbp": None,
            "sold_sample_size": None, "minimum_sold_sample_size": None, "cap_method": None,
            "observed_at": None, "evidence_source": None, "evidence_ref": None}
    if not saved or candidate is not saved.evidence_json.get("draft"):
        draft.update(version=(policy.version if policy else 0) + 1, definition_sha256=definition_hash(definition),
                     checkout_slot_parts=mappings, checkout_case=case_mapping,
                     required_part_keys=[part for _, part in mappings.values()] + ([case_mapping[1]] if case_mapping else []))
    valid, errors = draft_errors(draft)
    stale = bool(saved and candidate is saved.evidence_json.get("draft") and (
        saved.evidence_json.get("base_policy_version") != (policy.version if policy else 0)
        or draft.get("definition_sha256") != definition_hash(definition)))
    if stale:
        errors.insert(0, {"field": "draft", "message": "Saved draft is based on an older policy or build; rebuild it before saving"})
    assessment = None
    assessment_policy = valid if not errors else policy
    if assessment_policy:
        capacity_ids = await current_capacity_ids(db)
        body = SimpleNamespace(curated_build_id=cell_id, capacity_evidence_ids=capacity_ids, nonnew_consent=False,
            model_dump=lambda **_: {"playbook_id": playbook_id,"curated_build_id":cell_id,
                                   "capacity_evidence_ids":capacity_ids,"nonnew_consent":False})
        assessment, _ = await assess_stored_cell(db, parent, definition, assessment_policy, body)
    return {"cell_id": cell_id, "playbook_id": playbook_id, "name": definition["name"],
        "definition_sha256": definition_hash(definition), "base_policy_version": policy.version if policy else 0,
        "draft_id": saved.id if saved else None, "draft": draft, "draft_errors": errors,
        "draft_complete": valid is not None and not errors and not stale, "draft_stale": stale, "catalogue_error": catalogue_error,
        "catalogue_blockers": catalogue_blockers, "catalogue_parts_total_gbp": listing_cost_total(parts),
        "parts": parts, "cases": [{"id": row.id,"name":f"{row.brand} {row.name}"} for row in cases],
        "assessment": assessment, "price_review_sha256": price_review_hash(assessment), "checkout_enabled": bool(policy and policy.checkout_enabled)}


async def catalogue_part(db, role, slot_id, variant, listing, key, planned):
    source = await source_preview(db, listing) if listing else None
    item = source.get("item_gbp") if source else str(listing.price) if listing and listing.price is not None else None
    captured_postage = source.get("delivery_gbp") if source and source.get("postage_verified") is True else None
    # The owner's costing rule is £0 when buying postage was not captured.
    # Keep the source preview nullable/unverified; expose the assumption separately.
    postage = captured_postage if captured_postage is not None else "0.00"
    return {"role": role, "slot_id": slot_id, "variant_id": variant.id if variant else None,
        "title": listing.title if listing else "Choose a product from the catalogue",
        "planned_title": planned, "part_key": key, "source": source,
        "listing_url": listing.url if listing else None,
        "listed_item_gbp": item, "supplier_postage_gbp": postage,
        "supplier_postage_assumption": "captured" if captured_postage is not None else "owner-approved-zero-fallback",
        "listed_total_gbp": str(Decimal(item) + Decimal(postage)) if item is not None else None,
        "price_observed_at": source.get("observed_at") if source else utc(listing.last_seen_at).isoformat() if listing and listing.last_seen_at else None,
        "catalogue_status": variant.status if variant else None,
        "catalogue_price_gbp": str(variant.display_price) if variant else None}


def listing_cost_total(parts):
    # Unknown buying postage is already represented as the approved £0 cost
    # fallback by catalogue_part. Only a missing selected item price blocks the total.
    values = [part.get("listed_total_gbp") for part in parts]
    if not values or any(value is None for value in values):
        return None
    return str(sum((Decimal(value) for value in values), Decimal(0)))
