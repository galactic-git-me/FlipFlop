"""Admin-only economic assessments; these do not create customer offers."""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.admin_user import AdminUser
from app.models.commerce_evidence import PriceQuoteSnapshot, SupplierOfferEvidence
from app.routes.admin_auth import get_current_admin
from app.services.commerce_pricing import Condition, ConditionPolicy, CostStack, FulfilmentMode, MarketEvidence, SupplierOffer, eligible_offers, evaluate_price
from app.services.gem_economics import GemCosts, assess_gem
from app.services.procurement_optimizer import ApprovedPart, optimise_bom

router = APIRouter(prefix="/commerce-intelligence", tags=["commerce-intelligence"], dependencies=[Depends(get_current_admin)])


class CostStackInput(BaseModel):
    landed_parts: Decimal = Field(ge=0)
    build_labour: Decimal = Field(ge=0)
    packaging: Decimal = Field(ge=0)
    outbound_delivery: Decimal = Field(ge=0)
    payment_cost: Decimal = Field(ge=0)
    warranty_reserve: Decimal = Field(ge=0)
    returns_reserve: Decimal = Field(ge=0)
    expected_failure_cost: Decimal = Field(ge=0)
    allocated_overhead: Decimal = Field(ge=0)
    other_variable_costs: Decimal = Field(default=Decimal("0"), ge=0)


class MarketEvidenceInput(BaseModel):
    condition: Condition
    sold_median_gbp: Decimal | None = Field(default=None, ge=0)
    sold_sample_size: int = Field(ge=0)
    observed_at: str | None = None
    active_median_gbp: Decimal | None = Field(default=None, ge=0)


class PriceAssessmentRequest(BaseModel):
    costs: CostStackInput
    market: MarketEvidenceInput
    condition: Condition
    minimum_contribution_gbp: Decimal = Field(ge=0)
    minimum_margin_fraction: Decimal = Field(ge=0, lt=1)
    premium_gbp: Decimal = Field(default=Decimal("0"), ge=0)


class SupplierOfferEvidenceInput(BaseModel):
    part_key: str = Field(min_length=1, max_length=160)
    supplier: str = Field(min_length=1, max_length=160)
    channel: str = Field(pattern="^(retail|marketplace)$")
    condition: Condition
    item_gbp: Decimal = Field(ge=0)
    delivery_gbp: Decimal = Field(ge=0)
    fees_gbp: Decimal = Field(ge=0)
    risk_gbp: Decimal = Field(ge=0)
    observed_at: datetime
    stock_confirmed: bool
    delivery_working_days: int | None = Field(default=None, ge=0)
    supplier_confidence: Decimal = Field(default=Decimal("1"), ge=0, le=1)
    evidence_source: str = Field(min_length=1, max_length=160)
    evidence_ref: str = Field(min_length=1, max_length=500)


@router.post("/supplier-offers", status_code=201)
async def capture_supplier_offer(
    body: SupplierOfferEvidenceInput,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    observed_at = body.observed_at
    if observed_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="observed_at must include a timezone")
    if observed_at > datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="observed_at cannot be in the future")
    row = SupplierOfferEvidence(
        part_key=body.part_key, supplier=body.supplier, channel=body.channel,
        condition=body.condition.value, item_gbp=body.item_gbp, delivery_gbp=body.delivery_gbp,
        fees_gbp=body.fees_gbp, risk_gbp=body.risk_gbp, observed_at=observed_at,
        stock_confirmed=body.stock_confirmed, delivery_working_days=body.delivery_working_days,
        supplier_confidence=body.supplier_confidence, evidence_source=body.evidence_source,
        evidence_ref=body.evidence_ref, captured_by_admin_id=admin.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "part_key": row.part_key, "status": "captured", "captured_at": row.captured_at.isoformat()}


class QuoteSnapshotRequest(BaseModel):
    product_key: str = Field(min_length=1, max_length=160)
    required_part_keys: list[str] = Field(min_length=1)
    supplier_offer_ids: list[int] = Field(min_length=1)
    costs: CostStackInput
    market: MarketEvidenceInput
    market_evidence_source: str = Field(min_length=1, max_length=160)
    market_evidence_ref: str = Field(min_length=1, max_length=500)
    condition: Condition
    fulfilment_mode: FulfilmentMode
    condition_policy: ConditionPolicy
    nonnew_consent: bool = False
    minimum_contribution_gbp: Decimal = Field(ge=0)
    minimum_margin_fraction: Decimal = Field(ge=0, lt=1)
    premium_gbp: Decimal = Field(default=Decimal("0"), ge=0)


@router.post("/quote-snapshots", status_code=201)
async def create_quote_snapshot(
    body: QuoteSnapshotRequest,
    db: AsyncSession = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    if len(set(body.supplier_offer_ids)) != len(body.supplier_offer_ids):
        raise HTTPException(status_code=422, detail="supplier_offer_ids must be unique")
    result = await db.execute(select(SupplierOfferEvidence).where(SupplierOfferEvidence.id.in_(body.supplier_offer_ids)))
    rows = list(result.scalars().all())
    if len(rows) != len(body.supplier_offer_ids):
        raise HTTPException(status_code=422, detail="One or more supplier offer evidence records do not exist")
    offers = [SupplierOffer(
        supplier=row.supplier, channel=row.channel, condition=Condition(row.condition),
        item_gbp=Decimal(row.item_gbp), delivery_gbp=Decimal(row.delivery_gbp), fees_gbp=Decimal(row.fees_gbp),
        risk_gbp=Decimal(row.risk_gbp), observed_at=row.observed_at.isoformat(), stock_confirmed=row.stock_confirmed,
        approved=True, delivery_working_days=row.delivery_working_days,
        supplier_confidence=Decimal(row.supplier_confidence),
    ) for row in rows]
    eligible = eligible_offers(
        offers, body.fulfilment_mode, body.condition_policy, body.nonnew_consent,
        # Workshop capacity has no persisted evidence source yet. Keep
        # Priority closed until that gate is connected to real capacity.
        priority_capacity=False,
    )
    part_keys = [row.part_key for row in rows]
    required_keys = body.required_part_keys
    if (
        len(set(required_keys)) != len(required_keys)
        or len(set(part_keys)) != len(part_keys)
        or set(part_keys) != set(required_keys)
        or len(eligible) != len(rows)
    ):
        return await _save_quote_snapshot(
            db, body, admin, rows, None,
            {"offerable": False, "reason": "Supplier evidence is stale, incomplete, mismatched, or ineligible for this fulfilment mode"},
        )

    costs_input = CostStack(**body.costs.model_dump())
    costs = CostStack(**{
        **costs_input.__dict__,
        "landed_parts": sum((offer.landed_gbp + offer.risk_gbp for offer in eligible), Decimal("0")),
    })
    market = MarketEvidence(**body.market.model_dump())
    decision = evaluate_price(
        costs, market, body.condition, body.minimum_contribution_gbp,
        body.minimum_margin_fraction, premium_gbp=body.premium_gbp,
    )
    result_json = {
        "offerable": decision.offerable,
        "price_gbp": str(decision.price_gbp) if decision.price_gbp is not None else None,
        "required_base_gbp": str(decision.required_base_gbp),
        "true_cost_gbp": str(costs.true_cost),
        "reason": decision.reason,
    }
    return await _save_quote_snapshot(db, body, admin, rows, costs, result_json)


async def _save_quote_snapshot(db, body, admin, rows, costs, decision) -> dict:
    evidence = {
        "request": body.model_dump(mode="json"),
        "supplier_offers": [{
            "id": row.id, "part_key": row.part_key, "supplier": row.supplier, "channel": row.channel,
            "condition": row.condition, "item_gbp": str(row.item_gbp), "delivery_gbp": str(row.delivery_gbp),
            "fees_gbp": str(row.fees_gbp), "risk_gbp": str(row.risk_gbp), "observed_at": row.observed_at.isoformat(),
            "stock_confirmed": row.stock_confirmed, "evidence_source": row.evidence_source, "evidence_ref": row.evidence_ref,
        } for row in rows],
        "calculated_costs": {key: str(value) for key, value in costs.__dict__.items()} if costs else None,
    }
    status = "offerable" if decision["offerable"] else "not_offerable"
    snapshot = PriceQuoteSnapshot(
        product_key=body.product_key, status=status, evidence_json=evidence,
        decision_json=decision, created_by_admin_id=admin.id,
    )
    db.add(snapshot)
    await db.commit()
    await db.refresh(snapshot)
    return {"status": status, "quote_snapshot_id": snapshot.id, **decision}


@router.post("/price-assessment")
def price_assessment(body: PriceAssessmentRequest) -> dict:
    costs = CostStack(**body.costs.model_dump())
    market = MarketEvidence(**body.market.model_dump())
    decision = evaluate_price(
        costs, market, body.condition, body.minimum_contribution_gbp,
        body.minimum_margin_fraction, premium_gbp=body.premium_gbp,
    )
    return {
        "offerable": decision.offerable,
        "price_gbp": decision.price_gbp,
        "required_base_gbp": decision.required_base_gbp,
        "true_cost_gbp": costs.true_cost,
        "reason": decision.reason,
        "status": "assessment_only",
    }


class GemCostsInput(BaseModel):
    asking_price: Decimal = Field(ge=0)
    inbound_delivery: Decimal = Field(ge=0)
    buyer_protection: Decimal = Field(ge=0)
    repairs_and_upgrades: Decimal = Field(ge=0)
    build_labour: Decimal = Field(ge=0)
    outbound_delivery: Decimal = Field(ge=0)
    marketplace_fees: Decimal = Field(ge=0)
    warranty_and_returns_reserve: Decimal = Field(ge=0)
    risk_reserve: Decimal = Field(ge=0)


class GemAssessmentRequest(BaseModel):
    costs: GemCostsInput
    conservative_resale_gbp: Decimal = Field(ge=0)
    minimum_net_contribution_gbp: Decimal = Field(ge=0)
    estimated_days_to_sell: int | None = Field(default=None, gt=0)
    remaining_speculative_budget_gbp: Decimal = Field(ge=0)
    sold_sample_size: int = Field(ge=0)


@router.post("/gem-assessment")
def gem_assessment(body: GemAssessmentRequest) -> dict:
    return assess_gem(
        GemCosts(**body.costs.model_dump()), body.conservative_resale_gbp,
        body.minimum_net_contribution_gbp, body.estimated_days_to_sell,
        body.remaining_speculative_budget_gbp, sold_sample_size=body.sold_sample_size,
    )


class ProcurementAssessmentRequest(BaseModel):
    hard_minimums: dict
    candidates: list[ApprovedPart]
    mode: FulfilmentMode
    condition_policy: ConditionPolicy
    nonnew_consent: bool = False
    priority_capacity: bool = False
    parts_cost_ceiling_gbp: Decimal | None = Field(default=None, ge=0)


@router.post("/procurement-assessment")
def procurement_assessment(body: ProcurementAssessmentRequest) -> dict:
    plan = optimise_bom(
        body.hard_minimums, body.candidates, body.mode, body.condition_policy,
        body.nonnew_consent, priority_capacity=body.priority_capacity,
        parts_cost_ceiling_gbp=body.parts_cost_ceiling_gbp,
    )
    return {"status": "assessment_only", "plan": plan}
