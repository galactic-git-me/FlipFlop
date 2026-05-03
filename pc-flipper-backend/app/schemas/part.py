from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from app.models.part import PartCategory, PartCondition


class PartCreate(BaseModel):
    name: str
    brand: Optional[str] = None
    model: Optional[str] = None
    category: PartCategory
    condition: PartCondition = PartCondition.used
    specs: Optional[str] = None
    source_site: Optional[str] = None
    source_url: Optional[str] = None
    price: Optional[float] = None
    price_new: Optional[float] = None
    price_used: Optional[float] = None
    price_refurb: Optional[float] = None
    image_url: Optional[str] = None
    theme: Optional[str] = None
    resale_value_add: float = 0.0


class PartOut(PartCreate):
    id: int
    is_active: bool
    last_price_update: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
