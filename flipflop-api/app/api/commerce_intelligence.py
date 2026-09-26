"""Admin-only economic assessments; these do not create customer offers."""
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.routes.admin_auth import get_current_admin
from app.services.commerce_pricing import Condition, CostStack, MarketEvidence, evaluate_price
from app.services.gem_economics import GemCosts, assess_gem

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
