"""Quote generation schemas for PC build recommendations."""
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional


class QuoteRequest(BaseModel):
    """Request for generating a PC build quote."""

    budget: float = Field(..., ge=800, le=3000, description="Budget in GBP (800-3000)")


class ComponentLine(BaseModel):
    """Single component line in a quote."""

    component_type: str = Field(..., description="Component type (cpu, gpu, ram, etc)")
    component_category: str = Field(..., description="Component category (CPU, GPU, Memory, etc)")
    component_name: str = Field(..., description="Component model/name")
    price: float = Field(..., ge=0, description="Component price in GBP")
    quantity: int = Field(default=1, ge=1, description="Quantity")


class QuoteResponse(BaseModel):
    """Complete quote response with pricing breakdown."""

    budget: float = Field(..., description="Original customer budget in GBP")
    tier_name: str = Field(..., description="Budget tier name (e.g., 'Budget Gaming')")
    recommended_specs: Dict[str, str] = Field(..., description="Recommended component specs")
    components: List[ComponentLine] = Field(..., description="List of components with prices")
    parts_cost_total: float = Field(..., ge=0, description="Total cost of all components")
    labor_cost: float = Field(..., ge=0, description="Labor cost (3.5 hours @ £25/hr)")
    overhead_cost: float = Field(..., ge=0, description="Overhead cost (10% of parts + labor)")
    subtotal: float = Field(..., ge=0, description="Subtotal (parts + labor)")
    total_price: float = Field(..., ge=0, description="Total quote price including overhead")
    estimated_build_days: int = Field(default=7, ge=1, description="Estimated build time in days")
    budget_remaining: float = Field(..., description="Remaining budget (budget - total_price)")
    within_budget: bool = Field(..., description="Whether quote is within customer budget")


class BudgetTier(BaseModel):
    """A single budget tier definition."""

    budget: int = Field(..., description="Budget amount in GBP")
    name: str = Field(..., description="Tier name (e.g., 'Budget Gaming')")
    specs: Dict[str, str] = Field(..., description="Component recommendations for this tier")


class BudgetTiersResponse(BaseModel):
    """Response with all available budget tiers."""

    tiers: List[BudgetTier] = Field(..., description="List of all available budget tiers")
    min_budget: int = Field(..., description="Minimum budget in GBP")
    max_budget: int = Field(..., description="Maximum budget in GBP")
