"""Bounded MVP maintenance. Owner media decisions are never automated."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

DEFAULT_SUPPLIERS = ("amazon.co.uk", "overclockers.co.uk", "royalcdkeys.com", "gamers-outlet.net", "releases.ubuntu.com")


def mvp_mode(parent):
    return ((parent.pricing_model or {}).get("mvp_autonomy") or {}).get("profile") == "matrix_mvp"


def mvp_enabled(parent):
    return bool(((parent.pricing_model or {}).get("mvp_autonomy") or {}).get("enabled"))


def trusted_url(url, domains=DEFAULT_SUPPLIERS):
    try:
        parsed = urlsplit(url or "")
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and not parsed.username and not parsed.password and any(
            host == domain or host.endswith("." + domain) for domain in domains)
    except ValueError:
        return False


def publication_limit_reason(parent, definition, offer):
    rules = (parent.pricing_model or {}).get("mvp_autonomy") or {}
    if not rules.get("enabled"):
        return "Automatic publication is disabled"
    try:
        price = Decimal(str(offer["delivery_products"]["standard"]["recommended_price_gbp"]))
        ceiling = Decimal(str((rules.get("budget_ceilings") or {}).get(definition["id"])))
        anchor = (rules.get("price_anchors") or {}).get(definition["id"])
        previous = (((parent.pricing_model or {}).get("managed_offers") or {}).get(definition["id"]) or {})
        old_price = anchor or (previous.get("delivery_products", {}).get("standard", {}).get("recommended_price_gbp"))
        if not price.is_finite() or not ceiling.is_finite() or not 0 < price <= ceiling:
            return "The build exceeds its configured budget ceiling"
        if old_price is not None:
            old = Decimal(str(old_price))
            movement = Decimal(str(rules.get("max_price_change_fraction", "0.10")))
            if not old.is_finite() or old <= 0 or abs(price - old) / old > movement:
                return "The price moved beyond the enabled automatic pricing range"
    except (KeyError, TypeError, ValueError, InvalidOperation):
        return "Set this cell's budget ceiling in the operating rules before automatic publication"
    if any(not trusted_url(part.get("source_url")) for part in offer.get("components", [])):
        return "A selected supplier is outside the approved MVP supplier list"
    return None


def source_facts_can_be_verified(suggestion, now=None):
    if (not suggestion or suggestion.get("status") != "review_ready"
            or suggestion.get("conflicted_fields")
            or suggestion.get("reviewed_value_changes") or not suggestion.get("suggested_specs")
            or not trusted_url(suggestion.get("source_url"))):
        return False
    try:
        captured_at = suggestion.get("captured_at")
        if not isinstance(captured_at, str):
            return False
        captured = datetime.fromisoformat(captured_at.replace("Z", "+00:00"))
        now = now or datetime.now(timezone.utc)
        return captured.tzinfo is not None and timedelta(0) <= now - captured <= timedelta(days=30)
    except (KeyError, TypeError, ValueError):
        return False


def commercial_revision_payload(offer):
    """Keep revisions stable across recaptures of unchanged commercial facts.

    Observation IDs, scrape timestamps, freshness and engineering-review
    bookkeeping are provenance/health metadata. The approval path rebuilds
    the offer and rechecks exact current source evidence, so these volatile
    fields must not invalidate a review by themselves. Price, stock, condition,
    delivery ETA, postage proof, selected products and compatibility outcomes
    remain in the revision and still trigger a new review.
    """
    from copy import deepcopy
    result=deepcopy(offer)
    # The advisory LLM result is stored alongside a proposal after its
    # commercial revision is calculated. It is not publication authority and
    # must not make a freshly rebuilt revision differ from the saved one.
    result.pop("compatibility_review", None)
    volatile_source_fields={
        "observed_at", "price_observed_at", "fresh", "observation_id",
        "capture_refresh_warning", "last_capture_attempt",
    }
    def strip_capture_metadata(value):
        if isinstance(value,dict):
            return {key:strip_capture_metadata(item) for key,item in value.items()
                    if key not in volatile_source_fields}
        if isinstance(value,list):
            return [strip_capture_metadata(item) for item in value]
        return value
    result=strip_capture_metadata(result)
    for part in result.get("components",[]):
        for key in ("model_generation_status","media_ready","not_live_reason"):
            part.pop(key,None)
        # Candidate loading can resolve the same reviewed manufacturer/source
        # facts through different paths (scheduled refresh vs approval). Keep
        # the actual engineering values in the revision, while excluding the
        # resolver's timestamp, actor and completeness annotations. Those
        # annotations do not change fit and previously made every approval
        # appear stale even when the selected parts and compatibility result
        # were unchanged.
        engineering_metadata={"reviewed_at","reviewed_by","source_fingerprint",
            "missing_source_fields","engineering_reference",
            "manufacturer_verified_fields","primary_source_resolutions"}
        for field in ("engineering","planning_engineering"):
            facts=part.get(field)
            if isinstance(facts,dict):
                part[field]={key:value for key,value in facts.items()
                    if key not in engineering_metadata}
    return result


async def prepare_candidates(db, parent, candidates, *, reconcile_prices=True):
    """Validate exact labelled facts, retain unknown/conflicting values as exceptions."""
    from app.models.listing import Listing
    from app.services.playbook_service import _playbook_engineering_suggestion
    from app.services.catalogue_price_import import import_current_catalogue_prices
    eligible = [dict(part) for part in candidates if trusted_url(part.get("source_url"))]
    for part in eligible:
        listing = await db.get(Listing, part["listing_id"])
        suggestion = _playbook_engineering_suggestion(listing, part["role"])
        if source_facts_can_be_verified(suggestion):
            raw = dict(listing.raw_specs or {})
            current = raw.get("configurator") or {}
            if not current.get("reviewed"):
                # Certify only captured values. An incomplete product record can
                # still prove its socket without proving its missing dimensions.
                # Do not promote unrelated, previously unreviewed draft values.
                raw["configurator"] = {**suggestion["suggested_specs"], "reviewed": True,
                    "source_url": suggestion["source_url"], "source_fingerprint": suggestion["fingerprint"],
                    "missing_source_fields": suggestion.get("missing_fields", []),
                    "reviewed_by": "automation:exact-source-rule", "reviewed_at": datetime.now(timezone.utc).isoformat()}
                listing.raw_specs = raw
            part["engineering"] = dict(raw.get("configurator") or {})
        from app.services.playbook_component_facts import resolve_primary_engineering
        part['engineering'] = resolve_primary_engineering(part)
        key = f"case:{part['case_catalogue_id']}" if part["role"] == "case" and part.get("case_catalogue_id") else f"variant:{part['variant_id']}"
        if reconcile_prices:
            await import_current_catalogue_prices(db, [{"role":part["role"], "part_key":key, "source":part.get("source_observation")}], 0)
    await db.flush()
    if reconcile_prices:
        return eligible
    prepared = {(part['listing_id'], part['role']): part for part in eligible}
    return [prepared.get((part['listing_id'], part['role']), part) for part in candidates]


async def withdraw_unsafe_offers(db, parents):
    """Pause only offers whose own current evidence fails; preserve paid order snapshots."""
    from types import SimpleNamespace
    from sqlalchemy import select
    from app.models.catalogue import CatalogueVariant
    from app.models.listing import Listing
    from app.models.curated_build_segment import CuratedBuildSegment
    from app.services.curated_build_policy import definitions
    from app.services.commercial_quote_evidence import assess_stored_cell
    from app.services.commercial_checkout import current_capacity_ids
    from app.services.commercial_readiness import source_preview_many
    from app.services.shared_variant_assets import approved_model_photos
    from app.services.playbook_service import invalidate_conflicting_product_engineering
    from app.services.studio_fit import engineering_specs, evaluate_playbook_fit as evaluate_fit
    from app.services.playbook_book import record_cell_event
    from app.schemas.commercial_quote import CellCommercialPolicy
    from pydantic import ValidationError
    definitions_by_id = {row["id"]:row for row in definitions()["builds"]}
    paused=[]
    for parent in parents.values():
        if not mvp_enabled(parent):
            continue
        pricing=dict(parent.pricing_model or {})
        policies=dict(pricing.get("commercial_cells") or {})
        for cell_id, old in (pricing.get("managed_offers") or {}).items():
            definition=definitions_by_id.get(cell_id)
            if not definition or definition["segment"] != parent.name:
                continue
            segment=(await db.execute(select(CuratedBuildSegment).where(
                CuratedBuildSegment.customer_type==parent.name,
                CuratedBuildSegment.budget_level==definition["tier"]))).scalar_one_or_none()
            if segment is None or not segment.is_live:
                continue
            rows=(await db.execute(select(CatalogueVariant,Listing).join(Listing,Listing.id==CatalogueVariant.listing_id)
                .where(CatalogueVariant.id.in_(list((segment.components or {}).values()))))).all()
            sources=await source_preview_many(db,[listing for _,listing in rows])
            reason=None
            engineering={};chassis=None
            roles={part["variant_id"]:part["role"] for part in old.get("components",[])}
            if len(rows)!=len(segment.components or {}):
                reason="A published component no longer has a catalogue link"
            for variant,listing in rows:
                role=roles.get(variant.id)
                source=sources.get(listing.id) or {}
                if (not role or variant.status!="active" or getattr(listing.status,"value",listing.status)!="active"
                        or not source.get("fresh") or not source.get("active_listing")
                        or source.get("stock_status")!="available" or not trusted_url(listing.url)):
                    reason="A published component's current supplier evidence is missing or unavailable"
                if role and not role.startswith("os"):
                    if not approved_model_photos(variant):
                        reason="A published component has no owner-approved product photos"
                    invalidate_conflicting_product_engineering(listing,role)
                    specs=engineering_specs(listing.raw_specs)
                    if role=="case":
                        chassis={**specs,"engineering":specs}
                    else:
                        engineering[role]=specs
            checks=evaluate_fit(engineering,chassis,gpu_required="gpu" in (segment.components or {}))
            if any(check["severity"] in {"error","unknown"} for check in checks):
                reason="The published build's current compatibility facts are incomplete or conflicting"
            try:
                policy=CellCommercialPolicy.model_validate(policies.get(cell_id) or {})
                body=SimpleNamespace(curated_build_id=cell_id,capacity_evidence_ids=await current_capacity_ids(db),nonnew_consent=False,
                    model_dump=lambda **_: {"curated_build_id":cell_id})
                assessment,_=await assess_stored_cell(db,parent,definition,policy,body)
                quote=assessment["modes"].get("standard") or {}
                if not quote.get("offerable") or Decimal(str(quote.get("price_gbp")))!=Decimal(str(segment.selling_price)):
                    reason="The published price no longer matches the current safe Standard quote"
            except (ValidationError,InvalidOperation,TypeError,ValueError):
                reason="The published commercial policy cannot be validated"
            if reason:
                before={"is_live":True,"checkout_enabled":bool((policies.get(cell_id) or {}).get("checkout_enabled"))}
                segment.is_live=False
                policies[cell_id]={**(policies.get(cell_id) or {}),"checkout_enabled":False}
                record_cell_event(db,cell_id,"offer_paused",reason,before,{"is_live":False,"checkout_enabled":False},0)
                paused.append({"cell_id":cell_id,"reason":reason})
        parent.pricing_model={**pricing,"commercial_cells":policies}
    return paused


async def maintain_offers(db, parents, offers):
    from fastapi import HTTPException
    from sqlalchemy import select
    from app.models.playbook import PlaybookProposal
    from app.services.curated_build_policy import definitions
    from app.services.playbook_service import approve_proposal, SOURCE
    definitions_by_id = {row["id"]: row for row in definitions()["builds"]}
    paused=await withdraw_unsafe_offers(db,parents)
    published, exceptions = [], []
    for offer in offers:
        parent = parents.get(offer["segment"])
        if parent is None or not mvp_enabled(parent):
            continue
        cell_id = offer["cell_id"]
        reason = publication_limit_reason(parent, definitions_by_id[cell_id], offer)
        if offer["blockers"] or reason:
            exceptions.append({"cell_id":cell_id, "reason":reason or offer["blockers"][0]})
            continue
        proposal = (await db.execute(select(PlaybookProposal).where(
            PlaybookProposal.playbook_id == parent.id, PlaybookProposal.status == "pending",
            PlaybookProposal.action == "UPDATE").order_by(PlaybookProposal.id.desc()))).scalars().all()
        proposal = next((row for row in proposal if (row.demand_signals or {}).get("source") == SOURCE
            and (row.proposed_data or {}).get("cell_id") == cell_id), None)
        if not proposal:
            continue
        try:
            async with db.begin_nested():
                await approve_proposal(db, proposal.id, offer["revision_sha256"], 0)
                pricing = dict(parent.pricing_model or {})
                rules = dict(pricing["mvp_autonomy"])
                anchors = dict(rules.get("price_anchors") or {})
                anchors.setdefault(cell_id, offer["delivery_products"]["standard"]["recommended_price_gbp"])
                parent.pricing_model = {**pricing, "mvp_autonomy":{**rules,"price_anchors":anchors}}
            published.append(cell_id)
        except HTTPException as error:
            await db.refresh(parent)
            exceptions.append({"cell_id":cell_id,"reason":error.detail})
    return {"published":published,"paused":paused,"exceptions":exceptions}
