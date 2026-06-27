from datetime import datetime
from pydantic import BaseModel


class InventoryAllocationIn(BaseModel):
    """Schema for creating or updating inventory allocations (POST/PUT)."""
    inventory_item_id: int
    flip_id: int
    quantity_allocated: int
    notes: str | None = None


class InventoryAllocationPartialIn(BaseModel):
    """Schema for partial updates (PATCH) - all fields optional."""
    inventory_item_id: int | None = None
    flip_id: int | None = None
    quantity_allocated: int | None = None
    notes: str | None = None


class InventoryAllocationOut(BaseModel):
    """Schema for inventory allocation responses."""
    id: int
    inventory_item_id: int
    flip_id: int
    quantity_allocated: int
    cost_per_unit_at_allocation: float
    total_allocated_cost: float
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
