import json
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.manual_build import ManualBuild
from app.schemas.manual_build import (
    ManualBuildCreate, ManualBuildPatch, ManualBuildOut, ManualBuildSummary,
    EvaluationResult, EvaluationSuggestion,
)
from app.services import ai_service

router = APIRouter(prefix="/manual-builds", tags=["manual-builds"])


@router.post("/", response_model=ManualBuildOut, status_code=201)
async def create_build(body: ManualBuildCreate, db: AsyncSession = Depends(get_db)):
    build = ManualBuild(name=body.name, components=[], total_cost=None)
    db.add(build)
    await db.flush()
    await db.refresh(build)
    return build


@router.get("/", response_model=list[ManualBuildSummary])
async def list_builds(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ManualBuild).order_by(ManualBuild.updated_at.desc())
    )
    builds = result.scalars().all()
    return [
        ManualBuildSummary(
            id=b.id,
            name=b.name,
            total_cost=b.total_cost,
            component_count=len(b.components or []),
            updated_at=b.updated_at,
        )
        for b in builds
    ]


@router.get("/{build_id}", response_model=ManualBuildOut)
async def get_build(build_id: int, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    return build


@router.patch("/{build_id}", response_model=ManualBuildOut)
async def patch_build(build_id: int, body: ManualBuildPatch, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if body.name is not None:
        build.name = body.name
    if body.components is not None:
        build.components = [c.model_dump() for c in body.components]
        build.total_cost = sum(c.price_paid for c in body.components)
    build.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(build)
    return build


@router.delete("/{build_id}", status_code=204)
async def delete_build(build_id: int, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    await db.delete(build)


@router.post("/{build_id}/evaluate", response_model=EvaluationResult)
async def evaluate_build(build_id: int, db: AsyncSession = Depends(get_db)):
    build = await db.get(ManualBuild, build_id)
    if not build:
        raise HTTPException(404, "Build not found")
    if not build.components:
        raise HTTPException(400, "Build has no components to evaluate")

    # Format component list for the prompt
    lines = []
    for c in build.components:
        name = c["name"] if isinstance(c, dict) else c.name
        slot = c["slot"] if isinstance(c, dict) else c.slot
        price = c["price_paid"] if isinstance(c, dict) else c.price_paid
        lines.append(f"  - {slot}: {name} (paid £{price:.0f})")
    component_text = "\n".join(lines)
    total = build.total_cost or sum(
        (c["price_paid"] if isinstance(c, dict) else c.price_paid)
        for c in build.components
    )

    prompt = f"""I have assembled a PC build for resale in the UK secondhand market. Here are the components and what I paid:

{component_text}

Total cost: £{total:.0f}

Please assess this build and respond with ONLY valid JSON (no markdown, no code fences) in this exact format:
{{
  "low": <number>,
  "mid": <number>,
  "high": <number>,
  "narrative": "<2-3 sentence assessment>",
  "suggestions": [
    {{"text": "<actionable suggestion>", "uplift": <number>}},
    {{"text": "<actionable suggestion>", "uplift": <number>}},
    {{"text": "<actionable suggestion>", "uplift": <number>}}
  ]
}}

low/mid/high = estimated resale prices in GBP. uplift = estimated price increase in GBP from that suggestion. Max 3 suggestions. Be realistic about UK eBay/Gumtree prices."""

    response_text, _model = await ai_service.chat(prompt, history=[])

    # Parse JSON from response — strip any accidental markdown fences
    raw = response_text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Attempt to extract JSON object from response
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise HTTPException(502, f"LLM returned unparseable response: {raw[:200]}")
        data = json.loads(match.group())

    result = EvaluationResult(
        low=float(data.get("low", 0)),
        mid=float(data.get("mid", 0)),
        high=float(data.get("high", 0)),
        narrative=data.get("narrative", ""),
        suggestions=[
            EvaluationSuggestion(text=s["text"], uplift=float(s.get("uplift", 0)))
            for s in data.get("suggestions", [])[:3]
        ],
    )

    # Persist evaluation result back to the build
    build.last_evaluation = result.model_dump()
    build.updated_at = datetime.utcnow()
    await db.flush()

    return result
