from datetime import datetime
from pydantic import BaseModel, field_validator


class InventoryAllocationIn(BaseModel):
    """Schema for creating or updating inventory allocations (POST/PUT).
    Exactly one of flip_id or build_id must be provided."""
    inventory_item_id: int
    flip_id: int | None = None
    build_id: int | None = None
    quantity_allocated: int
    notes: str | None = None

    @field_validator("flip_id", "build_id")
    @classmethod
    def validate_target(cls, v, info):
        """Ensure exactly one of flip_id or build_id is set."""
        values = info.data
        flip = values.get("flip_id")
        build = values.get("build_id")
        if (flip is None and build is None) or (flip is not None and build is not None):
            raise ValueError("Exactly one of flip_id or build_id must be provided")
        return v


class InventoryAllocationPartialIn(BaseModel):
    """Schema for partial updates (PATCH) - all fields optional."""
    inventory_item_id: int | None = None
    flip_id: int | None = None
    build_id: int | None = None
    quantity_allocated: int | None = None
    notes: str | None = None


class InventoryAllocationOut(BaseModel):
    """Schema for inventory allocation responses."""
    id: int
    inventory_item_id: int
    flip_id: int | None
    build_id: int | None
    quantity_allocated: int
    cost_per_unit_at_allocation: float
    total_allocated_cost: float
    notes: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
