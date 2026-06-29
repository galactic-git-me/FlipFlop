"""
Schemas for Gem Build API requests and responses.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Any, Optional, List
from datetime import datetime


class ComponentSpec(BaseModel):
    """Individual component specification."""
    role: str = Field(..., description="Component type: cpu, gpu, ram, ssd, psu, case, cooler, motherboard")
    name: str = Field(..., description="Component name/model")
    quantity: int = Field(default=1, ge=1)


class GemSpecsIn(BaseModel):
    """PC build specifications for a gem."""
    cpu: str = Field(..., description="CPU model")
    gpu: str = Field(..., description="GPU model")
    ram_gb: int = Field(..., ge=8, le=192, description="RAM in GB")
    ram_type: str = Field(default="DDR5", description="DDR4 or DDR5")
    ssd_gb: int = Field(..., ge=256, le=4096, description="Primary SSD storage in GB")
    psu_watts: int = Field(..., ge=400, le=1200, description="Power supply wattage")
    case: str = Field(..., description="Case model/style")
    cooler: Optional[str] = Field(None, description="CPU cooler model")
    motherboard: Optional[str] = Field(None, description="Motherboard model")


class CostBreakdown(BaseModel):
    """Detailed cost breakdown for a gem."""
    cpu: float
    gpu: float
    ram: float
    ssd: float
    motherboard: float
    psu: float
    case: float
    cooler: float
    misc: float
    total_components: float
    labor: float
    overhead: float
    total: float


class GemRecommendationOut(BaseModel):
    """Single gem recommendation response."""
    id: int
    name: str = Field(..., description="Build name e.g., '1440p Gaming Beast'")
    use_case: str = Field(..., description="Target use case: gaming, workstation, streaming, office, etc.")
    target_budget: float = Field(..., description="Target customer budget in GBP")

    specs: Dict[str, Any] = Field(..., description="Full component specifications")
    estimated_cost: float = Field(..., description="Estimated cost to build (GBP)")
    estimated_price: float = Field(..., description="Estimated market selling price (GBP)")
    margin_gbp: float = Field(..., description="Expected profit in GBP")
    margin_percent: float = Field(..., description="Expected profit margin percentage (0-100)")

    confidence_score: int = Field(..., ge=0, le=100, description="Demand confidence 0-100%")
    risk_level: str = Field(..., description="low, medium, or high")
    recommended_quantity: int = Field(..., ge=1, le=3, description="How many units to build")
    reasoning: str = Field(..., description="Why this gem should be built now")

    cost_breakdown: Dict[str, float] = Field(..., description="Component cost breakdown")
    analysis_period_days: int = Field(default=30, description="Analysis period in days")

    generated_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GemRecommendationsResponse(BaseModel):
    """Response containing multiple gem recommendations."""
    generated_at: datetime
    analysis_period_days: int
    total_orders_analyzed: int
    demand_summary: Dict[str, Any] = Field(..., description="Summary of demand patterns found")
    recommendations: List[GemRecommendationOut] = Field(..., description="Array of gem recommendations")


class GemBuildActionIn(BaseModel):
    """Request to build a gem or apply action to it."""
    action: str = Field(..., description="'build' to create order, 'dismiss' to reject")
    quantity: Optional[int] = Field(default=1, ge=1, le=3, description="How many units to build")
    notes: Optional[str] = Field(None, max_length=500, description="Admin notes")


class GemBuildActionOut(BaseModel):
    """Response when building a gem or applying action."""
    status: str
    message: str
    gem_id: int
    action: str
    result: Optional[Dict[str, Any]] = None  # e.g., order_id if action='build'
