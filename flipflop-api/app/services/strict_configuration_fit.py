"""Strict reviewed-fact fit gate shared by Playbook approval and checkout."""
import json

from fastapi import HTTPException
from sqlalchemy import select

from app.models.catalogue import CatalogueVariant, CaseCatalogue, PlaybookSlot
from app.models.listing import Listing
from app.models.playbook import Playbook
from app.services.studio_fit import engineering_specs, evaluate_fit, evaluate_playbook_fit


async def configuration_fit(db, config):
    """Evaluate the selected catalogue rows, including unapproved draft builds.

    The public studio endpoint cannot be used for commercial review because it
    intentionally hides cells until publication. This service uses the same
    physical fit evaluator against the exact server-resolved selections.
    """
    from app.services.commercial_configuration import configuration_definition
    from app.services.playbook_component_facts import resolve_primary_engineering

    definition = await configuration_definition(db, config)
    selected = {int(slot_id): variant_id
                for slot_id, variant_id in definition["slot_selections"].items()}
    slot_rows = (await db.execute(select(PlaybookSlot).where(
        PlaybookSlot.id.in_(selected or {-1}),
        PlaybookSlot.playbook_id == config.playbook_id,
    ))).scalars().all()
    slots = {slot.id: slot for slot in slot_rows}
    variant_rows = (await db.execute(
        select(CatalogueVariant, Listing)
        .join(Listing, Listing.id == CatalogueVariant.listing_id)
        .where(CatalogueVariant.id.in_(set(selected.values()) or {-1}))
    )).all()
    variants = {variant.id: (variant, listing) for variant, listing in variant_rows}

    parts = {}
    missing = []
    for slot_id, variant_id in selected.items():
        slot = slots.get(slot_id)
        found = variants.get(variant_id)
        if slot is None or found is None or found[0].slot_id != slot_id:
            missing.append(f"catalogue selection for slot {slot_id}")
            continue
        role = slot.slot_type
        parts[role] = engineering_specs(found[1].raw_specs)
        if config.curated_build_id:
            raw_engineering=(found[1].raw_specs or {}).get('configurator') or {}
            parts[role]=resolve_primary_engineering({'role':role,'title':found[1].title,
                'engineering':{**parts[role],'reviewed_by':raw_engineering.get('reviewed_by','')}})

    playbook = await db.get(Playbook, config.playbook_id)
    requirements = playbook.requirements if playbook and isinstance(playbook.requirements, dict) else {}
    curated = bool(config.curated_build_id)
    authored = None
    if curated:
        from app.services.curated_build_policy import definitions
        authored = next((item for item in definitions()["builds"]
                         if item["id"] == config.curated_build_id
                         and item["segment"] == (playbook.name if playbook else None)), None)
    # Curated cells explicitly listing a GPU require one; cells without a GPU
    # must prove reviewed integrated graphics. Missing authored cells remain
    # conservative. Made-by-you follows the explicit Playbook policy.
    gpu_required = (
        bool(authored.get("components", {}).get('gpu')) and 'integrated' not in str(
            authored.get("components", {}).get('gpu','')).casefold() if authored is not None
        else requirements.get("gpu_required") is not False
    )
    if authored is None and curated:
        gpu_required = True

    required = {"cpu", "motherboard", "ram", "cooling", "psu"}
    if gpu_required:
        required.add("gpu")
    for role in required - parts.keys():
        missing.append(role)
    if not any(role == "storage" or role.startswith("storage_") for role in parts):
        missing.append("storage")

    case = await db.get(CaseCatalogue, config.case_id) if config.case_id else None
    if case is None or case.status != "active":
        missing.append("active case")
        case_data = None
    else:
        case_notes = {}
        if case.notes:
            try:
                case_notes = json.loads(case.notes)
            except (ValueError, TypeError):
                case_notes = {}
        case_data = {
            "form_factor": case.form_factor,
            "max_gpu_length_mm": case.max_gpu_length_mm,
            "max_cooler_height_mm": case.max_cooler_height_mm,
            "radiator_support": case.radiator_support,
            "engineering": engineering_specs(case_notes),
        }
        if curated and parts.get('case',{}).get('reviewed') is True:
            case_specs=parts['case']
            case_data={**case_data,**case_specs,'engineering':case_specs}

    evaluator=evaluate_playbook_fit if curated else evaluate_fit
    checks = evaluator(parts, case_data, gpu_required=gpu_required)
    for role in missing:
        checks.append({"code": "MISSING_CONFIGURATION", "severity": "error",
                       "message": f"Select a valid {role}.", "affected": [role]})
    return {"checks": checks, "gpu_required": gpu_required,
            "can_checkout": not missing and not any(
                item["severity"] in ("error", "unknown") for item in checks)}


async def require_configuration_fit(db, config):
    result = await configuration_fit(db, config)
    if not result["can_checkout"]:
        blockers = [item["message"] for item in result["checks"]
                    if item["severity"] in ("error", "unknown")]
        summary = "; ".join(blockers[:3]) or "Compatibility evidence is incomplete."
        raise HTTPException(409, f"This build is not ready for approval or checkout: {summary}")
    return result
