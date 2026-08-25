from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator


class AllocationInfo(BaseModel):
    """Info about a single allocation of an inventory item."""
    allocation_id: int
    flip_id: int | None = None
    build_id: int | None = None
    quantity_allocated: int


class InventoryItemIn(BaseModel):
    component_name: str
    component_type: str
    quantity: int = 1
    base_price: float | None = None
    shipping_cost: float = 0.0
    discount_amount: float = 0.0
    actual_cost: float | None = None  # For backward compatibility
    purchase_date: datetime | None = None
    source: str | None = None
    notes: str | None = None

    @model_validator(mode='before')
    @classmethod
    def resolve_base_price_from_actual_cost(cls, data):
        """If base_price is not provided but actual_cost is, use actual_cost as base_price."""
        if isinstance(data, dict):
            base_price = data.get('base_price')
            actual_cost = data.get('actual_cost')
            if base_price is None and actual_cost is not None:
                data['base_price'] = actual_cost
        return data

    @model_validator(mode='after')
    def validate_base_price_not_null(self):
        """Ensure base_price is not None after field resolution."""
        if self.base_price is None:
            raise ValueError("base_price or actual_cost must be provided")
        return self


class InventoryItemPartialIn(BaseModel):
    """Partial schema for PATCH updates - all fields optional."""
    component_name: str | None = None
    component_type: str | None = None
    quantity: int | None = None
    base_price: float | None = None
    shipping_cost: float | None = None
    discount_amount: float | None = None
    actual_cost: float | None = None  # For backward compatibility
    purchase_date: datetime | None = None
    source: str | None = None
    notes: str | None = None

    @model_validator(mode='before')
    @classmethod
    def resolve_base_price_from_actual_cost(cls, data):
        """If base_price is not provided but actual_cost is, use actual_cost as base_price."""
        if isinstance(data, dict):
            base_price = data.get('base_price')
            actual_cost = data.get('actual_cost')
            if base_price is None and actual_cost is not None:
                data['base_price'] = actual_cost
        return data


class InventoryItemOut(BaseModel):
    id: int
    component_name: str
    component_type: str
    quantity: int
    quantity_unallocated: int | None = None
    base_price: float
    shipping_cost: float
    discount_amount: float
    actual_cost: float
    purchase_date: datetime
    source: str | None
    notes: str | None
    created_at: datetime
    allocations: list[AllocationInfo] = []

    class Config:
        from_attributes = True
