from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal, Optional

ListingMode = Literal["active", "sold", "both"]


class SourceSearchTermCreate(BaseModel):
    scope: str = "cases"
    group_name: str
    term: str
    source_names: list[str] = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)
    notes: Optional[str] = None
    enabled: bool = True
    listing_mode: ListingMode = "active"


class SourceSearchTermUpdate(BaseModel):
    scope: Optional[str] = None
    group_name: Optional[str] = None
    term: Optional[str] = None
    source_names: Optional[list[str]] = None
    attributes: Optional[dict] = None
    notes: Optional[str] = None
    enabled: Optional[bool] = None
    listing_mode: Optional[ListingMode] = None
    demand_score: Optional[float] = None
    is_baseline: Optional[bool] = None
    zero_results_streak: Optional[int] = None


class SourceSearchTermOut(BaseModel):
    # Base fields from Create
    scope: str
    group_name: str
    term: str
    source_names: list[str]
    attributes: dict
    notes: Optional[str]
    enabled: bool
    listing_mode: ListingMode
    # New demand-driven fields
    demand_score: float
    is_baseline: bool
    # Read-only fields
    id: int
    created_at: datetime
    zero_results_streak: int
    last_result_at: Optional[datetime]

    model_config = {"from_attributes": True}
