"""Canonical, server-resolved identities for made-by-you and upgraded builds."""
from fastapi import HTTPException
from app.services.curated_build_policy import definitions
from app.services.commercial_quote_evidence import definition_hash
from app.services.playbook_pricing import apply_curated_cell_upgrades, InvalidBuildError


async def configuration_definition(db, config):
    try:
        selections = config.slot_selections
        if config.upgrade_candidate_indexes:
            selections, _ = await apply_curated_cell_upgrades(
                db, config.playbook_id, config.curated_build_id,
                config.slot_selections, config.upgrade_candidate_indexes,
            )
    except InvalidBuildError as exc:
        raise HTTPException(409, str(exc)) from exc
    cell = next((item for item in definitions()["builds"]
                 if item["id"] == config.curated_build_id), None)
    return {"playbook_id": config.playbook_id,
            "curated_build_id": config.curated_build_id,
            "budget_tier": config.budget_tier,
            "slot_selections": {str(key): value for key, value in selections.items()},
            "case_id": config.case_id,
            "curated_definition_sha256": definition_hash(cell) if cell else None}


def validate_configuration_policy(policy, definition):
    expected = {str(slot): variant for slot, (variant, _) in policy.checkout_slot_parts.items()}
    if (policy.definition_sha256 != definition_hash(definition)
            or expected != definition["slot_selections"]
            or not policy.checkout_case or policy.checkout_case[0] != definition["case_id"]
            or any(key != f"variant:{variant}" for variant, key in policy.checkout_slot_parts.values())
            or policy.checkout_case[1] != f"case:{definition['case_id']}"):
        raise HTTPException(409, "The pricing policy must match every selected component and case")
