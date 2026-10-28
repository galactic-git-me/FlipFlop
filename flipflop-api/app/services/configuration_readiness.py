"""Review exact customer selections without borrowing another PC's market evidence."""
from types import SimpleNamespace
from decimal import Decimal
from fastapi import HTTPException
from sqlalchemy import select
from app.models.app_settings import AppSettings
from app.models.catalogue import CatalogueVariant, CaseCatalogue, PlaybookSlot
from app.models.listing import Listing
from app.models.playbook import Playbook
from app.models.commerce_evidence import PriceQuoteSnapshot
from app.schemas.payment import PlaybookBuildConfig
from app.services.commercial_configuration import configuration_definition
from app.services.commercial_quote_evidence import definition_hash, assess_stored_cell
from app.services.commercial_readiness import draft_errors, catalogue_part, listing_cost_total, price_review_hash
from app.services.commercial_checkout import current_capacity_ids
from app.services.playbook_delivery import _checkout_build_mode
from app.services.playbook_pricing import price_playbook_build, InvalidBuildError


async def request_context(db, request_id, *, lock=False):
    request = await db.get(PriceQuoteSnapshot, request_id)
    if request is None or request.status != "configuration_review":
        raise HTTPException(404, "Configuration review not found")
    config = PlaybookBuildConfig.model_validate(request.evidence_json["build_config"])
    query = select(Playbook).where(Playbook.id == config.playbook_id, Playbook.status == "active")
    if lock:
        query = query.with_for_update()
    parent = (await db.execute(query)).scalar_one_or_none()
    if parent is None:
        raise HTTPException(404, "Active Playbook not found")
    definition = await configuration_definition(db, config)
    if definition != request.evidence_json["definition"]:
        raise HTTPException(409, "This configuration changed; request new delivery prices")
    try:
        await price_playbook_build(db, config.playbook_id, config.slot_selections,
            config.case_id, build_mode=_checkout_build_mode(config),
            curated_build_id=config.curated_build_id, upgrade_candidate_indexes=config.upgrade_candidate_indexes)
    except InvalidBuildError as exc:
        raise HTTPException(409, str(exc)) from exc
    return request, parent, config, definition


async def configuration_detail(db, request_id):
    request, parent, config, definition = await request_context(db, request_id)
    key = definition_hash(definition)
    old = ((parent.pricing_model or {}).get("commercial_configurations") or {}).get(key)
    mappings, parts = {}, []
    policy_parts = {}
    policy_part_keys = []
    for slot, variant_id in definition["slot_selections"].items():
        variant = await db.get(CatalogueVariant, variant_id)
        slot_model = await db.get(PlaybookSlot, int(slot))
        listing = await db.get(Listing, variant.listing_id)
        part_key = f"variant:{variant_id}"
        role = slot_model.slot_type
        mappings[slot] = [variant_id, part_key]
        policy_part_keys.append(part_key)
        part = await catalogue_part(db, role, int(slot), variant, listing, part_key, None)
        parts.append(part)
        policy_parts[role] = _policy_source_part(part, variant_id=variant_id,
            slot_id=int(slot), part_key=part_key)
    case = await db.get(CaseCatalogue, config.case_id)
    case_mapping = [case.id, f"case:{case.id}"]
    policy_part_keys.append(case_mapping[1])
    listing = (await db.execute(select(Listing).where(Listing.case_catalogue_id == case.id,
        Listing.status == "active").order_by(Listing.last_seen_at.desc(), Listing.id.desc()).limit(1))).scalar_one_or_none()
    part = await catalogue_part(db, 'case', None, None, listing, case_mapping[1], None)
    part.update(case_id=case.id, title=f'{case.brand} {case.name}')
    parts.append(part)
    policy_parts['case'] = _policy_source_part(part, case_id=case.id, part_key=case_mapping[1])
    version = (old or {}).get("version", 0)
    approved_exact = bool(old and old.get('checkout_enabled'))
    draft = dict(old) if approved_exact else None
    policy_blockers = []
    if draft is None:
        rule_definition = next((item for item in definitions()['builds']
            if item['id'] == config.curated_build_id and item['segment'] == parent.name), None)
        tier = config.budget_tier or (rule_definition or {}).get('tier')
        if tier not in {'Budget', 'Mid-range', 'High-end'}:
            policy_blockers.append('Choose a Playbook budget tier before the service can apply its approved pricing rules.')
        else:
            for part in parts:
                source = part.get('source') or {}
                if not _source_is_priced(source):
                    policy_blockers.append(f"{part['role']}: an exact current new-condition supplier capture with a valid item price is missing; unknown buying postage defaults to £0.00.")
            if not policy_blockers:
                from app.services.playbook_service import automatic_policy
                authored = rule_definition or {'id': f'exact:{key[:16]}', 'segment': parent.name,
                    'tier': tier, 'components': {}}
                settings = await db.get(AppSettings, 1)
                generated = automatic_policy(policy_parts, authored, parent, settings,
                    definition_sha256_override=key, include_market=False, version=version + 1)
                if generated is None:
                    policy_blockers.append('Approved Playbook pricing or delivery settings are incomplete.')
                else:
                    generated = generated.model_copy(update={'checkout_enabled': False,
                        'checkout_slot_parts': {int(slot): (value[0], value[1]) for slot, value in mappings.items()},
                        'checkout_case': tuple(case_mapping) if case_mapping else None,
                        'required_part_keys': policy_part_keys,
                        'market': None, 'market_tolerance_fraction': Decimal('0')})
                    draft = generated.model_dump(mode='json')
    if draft is not None:
        valid, errors = draft_errors(draft)
        assessment = await assess_configuration(db, parent, definition, valid) if valid and not errors else None
    else:
        errors = [{'field': 'policy', 'message': item} for item in policy_blockers]
        assessment = None
    return {"request_id": request_id, "playbook_id": parent.id, "name": parent.name,
            "curated_build_id": config.curated_build_id, "budget_tier": config.budget_tier,
            "base_policy_version": version, "draft_id": None,
            "definition_sha256": key, "draft": draft, "draft_errors": errors,
            "policy_blockers": policy_blockers,
            "parts": parts, "catalogue_parts_total_gbp": listing_cost_total(parts), "assessment": assessment,
            "price_review_sha256": price_review_hash(assessment),
            "checkout_enabled": approved_exact}


def _source_is_priced(source):
    if (not source.get('fresh') or not source.get('commercial_capture_verified')
            or source.get('condition') != 'new' or source.get('item_gbp') is None):
        return False
    try:
        item = Decimal(str(source['item_gbp']))
        if source.get('postage_verified') is True:
            if source.get('delivery_gbp') is None:
                return False
            postage = Decimal(str(source['delivery_gbp']))
        elif (source.get('postage_assumption') == 'owner-approved-zero-fallback'
                and Decimal(str(source.get('delivery_gbp'))) == 0):
            # The owner-approved fallback is a valid costing assumption. It
            # must not be presented as captured/free delivery evidence.
            postage = Decimal('0.00')
        else:
            return False
    except Exception:
        return False
    free_official_download = (
        source.get('evidence_kind') == 'official_free_software'
        and source.get('identity_source') == 'official_free_software'
        and source.get('source') == 'Ubuntu'
        and item == 0 and postage == 0
        and source.get('stock_status') == 'available'
    )
    return item.is_finite() and (item > 0 or free_official_download) and postage.is_finite() and postage >= 0


def _policy_source_part(part, *, part_key, variant_id=None, slot_id=None, case_id=None):
    source = part.get('source') or {}
    item, postage = source.get('item_gbp'), source.get('delivery_gbp')
    landed = Decimal(str(item)) + Decimal(str(postage)) if item is not None and postage is not None else None
    return {'role': part['role'], 'variant_id': variant_id, 'slot_id': slot_id,
        'case_catalogue_id': case_id, 'listing_id': source.get('listing_db_id'),
        'part_key': part_key, 'listing_price_gbp': item, 'supplier_postage_gbp': postage,
        'landed_gbp': str(landed) if landed is not None else None, 'source_observation': source}


async def assess_configuration(db, parent, definition, policy):
    capacities = await current_capacity_ids(db)
    body = SimpleNamespace(curated_build_id=definition["curated_build_id"],
        capacity_evidence_ids=capacities, nonnew_consent=False,
        model_dump=lambda **_: {"definition": definition, "capacity_evidence_ids": capacities,
                               "nonnew_consent": False})
    result, _ = await assess_stored_cell(db, parent, definition, policy, body)
    return result
