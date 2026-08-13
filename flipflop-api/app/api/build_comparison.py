"""Compare 2-5 of a customer's own orders/drafts side by side, with an
AI-generated tradeoff analysis."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.customer import Customer
from app.models.draft_build import DraftBuild
from app.models.order import Order
from app.routes.auth import get_current_user
from app.schemas.build_comparison import CompareBuildsIn, CompareBuildsOut, ComparedBuildOut, ComparisonSlotOut
from app.services.comparison_analysis_service import generate_comparison_analysis
from app.services.playbook_pricing import InvalidBuildError, price_playbook_build
from app.api.drafts import _price_draft

router = APIRouter(prefix="/api/builds", tags=["builds"])


def _parse_ref(ref: str) -> tuple[str, int]:
    try:
        kind, raw_id = ref.split(":", 1)
        if kind not in ("order", "draft"):
            raise ValueError
        return kind, int(raw_id)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail=f'Invalid ref "{ref}" — expected "order:{{id}}" or "draft:{{id}}"')


async def _load_order_as_compared(db: AsyncSession, order_id: int, customer_id: int) -> ComparedBuildOut:
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order or order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    specs = order.specs or {}
    return ComparedBuildOut(
        ref=f"order:{order_id}",
        kind="order",
        label=order.order_id,
        playbook_name=specs.get("playbook_name", "Custom build"),
        slots=[
            ComparisonSlotOut(slot_type=s["slot_type"], title=s["title"], price=s["price"])
            for s in specs.get("slots", [])
        ],
        case_name=specs.get("case_name"),
        case_price=specs.get("case_price", 0.0),
        total=order.customer_price,
    )


async def _load_draft_as_compared(db: AsyncSession, draft_id: int, customer_id: int) -> ComparedBuildOut:
    result = await db.execute(select(DraftBuild).where(DraftBuild.id == draft_id))
    draft = result.scalar_one_or_none()
    if not draft or draft.customer_id != customer_id:
        raise HTTPException(status_code=404, detail=f"Draft {draft_id} not found")

    try:
        priced = await _price_draft(db, draft)
    except InvalidBuildError as e:
        raise HTTPException(status_code=409, detail=f"Draft {draft_id} selection is no longer valid: {e}")

    return ComparedBuildOut(
        ref=f"draft:{draft_id}",
        kind="draft",
        label=priced.name or f"Draft #{draft_id}",
        playbook_name=priced.playbook_name,
        slots=[
            ComparisonSlotOut(slot_type=s.slot_type, title=s.title, price=s.price)
            for s in priced.slots
        ],
        case_name=priced.case_name,
        case_price=priced.case_price,
        total=priced.priced_total,
    )


@router.post("/compare", response_model=CompareBuildsOut)
async def compare_builds(
    request: CompareBuildsIn,
    customer: Customer = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    builds: list[ComparedBuildOut] = []
    for ref in request.refs:
        kind, ref_id = _parse_ref(ref)
        if kind == "order":
            builds.append(await _load_order_as_compared(db, ref_id, customer.id))
        else:
            builds.append(await _load_draft_as_compared(db, ref_id, customer.id))

    analysis = await generate_comparison_analysis(builds)
    return CompareBuildsOut(builds=builds, analysis=analysis)
