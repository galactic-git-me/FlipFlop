from datetime import datetime
from pydantic import BaseModel, field_validator, model_validator


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

    @field_validator('base_price', mode='before')
    @classmethod
    def resolve_base_price(cls, v, info):
        """If base_price is not provided but actual_cost is, use actual_cost as base_price."""
        if v is None and 'actual_cost' in info.data and info.data['actual_cost'] is not None:
            return info.data['actual_cost']
        return v

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

    @field_validator('base_price', mode='before')
    @classmethod
    def resolve_base_price(cls, v, info):
        """If base_price is not provided but actual_cost is, use actual_cost as base_price."""
        if v is None and 'actual_cost' in info.data and info.data['actual_cost'] is not None:
            return info.data['actual_cost']
        return v


class InventoryItemOut(BaseModel):
    id: int
    component_name: str
    component_type: str
    quantity: int
    base_price: float
    shipping_cost: float
    discount_amount: float
    actual_cost: float
    purchase_date: datetime
    source: str | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True
