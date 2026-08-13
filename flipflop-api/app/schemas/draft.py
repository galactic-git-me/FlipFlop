"""Pydantic schemas for saved draft builds."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DraftBuildIn(BaseModel):
    playbook_id: int = Field(..., gt=0)
    name: Optional[str] = Field(None, max_length=255)
    slot_selections: dict[int, int] = Field(default_factory=dict)
    case_id: Optional[int] = None
    chosen_week: Optional[str] = None


class DraftBuildSlotOut(BaseModel):
    slot_id: int
    slot_type: str
    variant_id: int
    title: str
    price: float


class DraftBuildOut(BaseModel):
    id: int
    playbook_id: int
    playbook_name: str
    name: Optional[str] = None
    slots: list[DraftBuildSlotOut] = Field(default_factory=list)
    case_id: Optional[int] = None
    case_name: Optional[str] = None
    case_price: float = 0.0
    chosen_week: Optional[str] = None
    priced_total: float
    created_at: datetime
    updated_at: Optional[datetime] = None
