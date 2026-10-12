"""Build Studio joins the existing public catalogue, pricing and compatibility.

No workbook prices, synthetic products, client amounts or private sourcing data.
"""
from dataclasses import asdict
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.playbook import Playbook
from app.api.public_catalogue import public_playbook_slots, public_list_cases
from app.services.configurator_compatibility import evaluate_configuration
from app.services.playbook_pricing import price_playbook_build, InvalidBuildError
from app.services.studio_fit import evaluate_fit

router = APIRouter(prefix='/public/studio', tags=['public-studio'])


class StudioSelection(BaseModel):
    playbook_id: int = Field(gt=0)
    selections: dict[int, int] = Field(default_factory=dict, max_length=30)
    case_id: int | None = None
    build_mode: Literal['custom', 'curated'] = 'custom'
    curated_build_id: str | None = None
    upgrade_candidate_indexes: list[int] = Field(default_factory=list, max_length=2)


@router.post('/evaluate')
async def evaluate_studio(body: StudioSelection, db: AsyncSession = Depends(get_db)):
    from app.api.public_catalogue import public_curated_slots, public_custom_slots
    from app.services.playbook_pricing import apply_curated_cell_upgrades
    try:
        effective_selections, _ = await apply_curated_cell_upgrades(
            db, body.playbook_id, body.curated_build_id, body.selections,
            body.upgrade_candidate_indexes,
        )
    except InvalidBuildError as exc:
        raise HTTPException(409, str(exc)) from exc
    playbook = await db.get(Playbook, body.playbook_id)
    playbook_requirements = playbook.requirements if playbook and isinstance(playbook.requirements, dict) else {}
    raw_gpu_required = playbook_requirements.get("gpu_required")
    # Missing or malformed Playbook data stays conservative. Only an explicit
    # boolean false makes dedicated graphics optional in Made-by-you. Curated
    # builds remain fixed, complete pre-approved specifications.
    is_curated = body.build_mode == "curated" or bool(body.curated_build_id)
    gpu_required = is_curated or raw_gpu_required is not False
    slots = await (
        public_curated_slots(body.playbook_id, db, body.curated_build_id)
        if is_curated
        else public_custom_slots(body.playbook_id, db)
    )
    cases = await public_list_cases(db)
    lookup = {slot['slot_id']: {v['id']: v for tier in slot['variants_by_tier'].values() for v in tier} for slot in slots}
    for slot_id, variant_id in effective_selections.items():
        if variant_id not in lookup.get(slot_id, {}):
            raise HTTPException(409, 'A selected part is no longer available in this catalogue. Refresh your build.')
    case = next((c for c in cases if c['id'] == body.case_id), None)
    if body.case_id is not None and case is None:
        raise HTTPException(409, 'The selected case is no longer available. Choose another case.')
    parts = {slot['slot_type']: lookup[slot['slot_id']][effective_selections[slot['slot_id']]].get('specifications', {})
             for slot in slots if slot['slot_id'] in effective_selections}
    checks = evaluate_fit(parts, case, gpu_required=gpu_required)
    missing = [slot['slot_type'] for slot in slots
               if slot['slot_id'] not in effective_selections
               and not (slot['slot_type'] == 'gpu' and not gpu_required)]
    # A desktop studio build requires every physical category, even when an
    # incomplete playbook has not published that slot yet.
    required_categories = ('cpu', 'motherboard', 'ram', 'storage', 'cooling', 'psu')
    if gpu_required:
        required_categories += ('gpu',)
    for category in required_categories:
        if category not in parts and category not in missing:
            missing.append(category)
    if case is None:
        missing.append('case')
    for category in missing:
        checks.append(dict(code='MISSING_' + category.upper(), severity='error', message=f'Select {category} to complete this build.', affected=[category]))
    legacy = {'slots': []} if not is_curated else await evaluate_configuration(db, body.playbook_id, effective_selections, body.case_id,
                                          catalogue_variant_ids=[v for variants in lookup.values() for v in variants])
    for slot in legacy['slots']:
        verdict = next((v for v in slot['variants'] if v['variant_id'] == effective_selections.get(slot['slot_id'])), None)
        if verdict and not verdict['is_compatible']:
            checks.append(dict(code=verdict.get('rule_code') or 'COMPATIBILITY', severity='error', message=verdict['reason'], affected=[slot['slot_type']]))
    price = None
    try:
        price = asdict(await price_playbook_build(db, body.playbook_id, body.selections, body.case_id, build_mode=body.build_mode, curated_build_id=body.curated_build_id, upgrade_candidate_indexes=body.upgrade_candidate_indexes))
    except InvalidBuildError as exc:
        checks.append(dict(code='AVAILABILITY', severity='error', message=str(exc), affected=[]))
    recommendations = []
    selected_gpu = any(
        slot['slot_type'] == 'gpu' and slot['slot_id'] in effective_selections
        for slot in slots
    )
    if not gpu_required and selected_gpu:
        recommendations.append({
            "code": "OPTIONAL_GPU_SPEND_REVIEW",
            "severity": "recommendation",
            "title": "Consider where the graphics budget helps most",
            "message": (
                f"The {playbook.name if playbook else 'selected Playbook'} does not require a dedicated GPU. "
                "You can keep your choice, but for this use case you may prefer to put more of the budget "
                "toward the CPU, memory or storage, or keep the total lower. Your selections have not changed."
            ),
            "affected": ["gpu", "cpu", "ram", "storage"],
        })
    return dict(checks=checks, recommendations=recommendations, gpu_required=gpu_required,
                price=price, verdicts=legacy['slots'],
                can_checkout=price is not None and not any(c['severity'] in ('error', 'unknown') for c in checks))
