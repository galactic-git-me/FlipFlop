"""Shared public Playbook delivery pricing, also used by payment checkout."""
from fastapi import HTTPException
from app.services.playbook_pricing import InvalidBuildError, price_playbook_build
from app.services.commercial_checkout import create_checkout_quote


def _checkout_build_mode(build_config) -> str:
    """Translate the storefront's flow marker into the server pricing mode."""
    mode = build_config.validation_mode
    curated = bool(build_config.curated_build_id)
    if curated:
        if mode not in (None, "curated"):
            raise HTTPException(status_code=422, detail="A curated cell cannot use the Made-by-you checkout mode")
        return "curated"
    if mode == "curated":
        raise HTTPException(status_code=422, detail="Choose a curated Playbook cell before using Curated-for-you checkout")
    if mode not in (None, "custom", "studio"):
        raise HTTPException(status_code=422, detail="Unsupported build checkout mode")
    if not build_config.budget_tier:
        raise HTTPException(status_code=422, detail="Choose a Playbook budget tier before ordering a Made-by-you build")
    return "custom"



async def quote_playbook_delivery(db, build_config):
    if build_config.case_id is None:
        raise HTTPException(422, "Select a case before comparing delivery prices")
    mode = _checkout_build_mode(build_config)
    try:
        await price_playbook_build(db, build_config.playbook_id, build_config.slot_selections,
            build_config.case_id, build_mode=mode, curated_build_id=build_config.curated_build_id,
            upgrade_candidate_indexes=build_config.upgrade_candidate_indexes)
    except InvalidBuildError as exc:
        raise HTTPException(409, str(exc)) from exc
    return await create_checkout_quote(db, build_config)
