"""Pydantic schemas for multi-build comparison."""

from pydantic import BaseModel, Field
from typing import Optional


class CompareBuildsIn(BaseModel):
    refs: list[str] = Field(
        ..., min_length=2, max_length=5,
        description='Each ref is "order:{id}" or "draft:{id}", scoped to the requesting customer.',
    )


class ComparisonSlotOut(BaseModel):
    slot_type: str
    title: str
    price: float


class ComparedBuildOut(BaseModel):
    ref: str
    kind: str  # "order" | "draft"
    label: str
    playbook_name: str
    slots: list[ComparisonSlotOut]
    case_name: Optional[str] = None
    case_price: float = 0.0
    total: float


class CompareBuildsOut(BaseModel):
    builds: list[ComparedBuildOut]
    analysis: str
