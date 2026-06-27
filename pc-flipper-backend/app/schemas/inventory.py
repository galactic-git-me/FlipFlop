from datetime import datetime
from pydantic import BaseModel


class InventoryItemIn(BaseModel):
    component_name: str
    component_type: str
    quantity: int = 1
    actual_cost: float
    purchase_date: datetime | None = None
    source: str | None = None
    notes: str | None = None


class InventoryItemOut(BaseModel):
    id: int
    component_name: str
    component_type: str
    quantity: int
    actual_cost: float
    purchase_date: datetime
    source: str | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True
