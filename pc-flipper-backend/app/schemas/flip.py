from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from app.models.flip import FlipStage
from app.schemas.listing import ListingOut


class FlipCreate(BaseModel):
    listing_id: int
    notes: Optional[str] = None


class FlipUpdate(BaseModel):
    stage: Optional[FlipStage] = None
    selected_upgrade_ids: Optional[dict[str, int]] = None
    notes: Optional[str] = None
    actual_sale_price: Optional[float] = None
    sale_platform: Optional[str] = None


class FlipOut(BaseModel):
    id: int
    listing_id: int
    listing: Optional[ListingOut] = None
    stage: FlipStage
    selected_upgrade_ids: dict
    base_cost: float
    upgrade_cost: float
    total_cost: float
    platform_fee_pct: float
    initial_estimated_resale: Optional[float]
    current_estimated_resale: Optional[float]
    initial_estimated_profit: Optional[float]
    current_estimated_profit: Optional[float]
    actual_sale_price: Optional[float]
    actual_profit: Optional[float]
    sale_platform: Optional[str]
    generated_title: Optional[str]
    notes: Optional[str]
    created_at: datetime
    sold_at: Optional[datetime]

    model_config = {"from_attributes": True}
