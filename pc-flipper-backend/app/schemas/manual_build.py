# pc-flipper-backend/app/schemas/manual_build.py
from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class BuildComponent(BaseModel):
    slot: str                        # "GPU", "CPU", "Base PC", etc.
    name: str
    price_paid: float
    source: str = "manual"           # "catalogue" | "manual"
    part_id: Optional[int] = None   # set when source == "catalogue"
    listing_url: Optional[str] = None
    image_url: Optional[str] = None


class ManualBuildCreate(BaseModel):
    name: str = "Untitled Build"


class ManualBuildPatch(BaseModel):
    name: Optional[str] = None
    components: Optional[list[BuildComponent]] = None


class EvaluationSuggestion(BaseModel):
    text: str
    uplift: float


class EvaluationResult(BaseModel):
    low: float
    mid: float
    high: float
    narrative: str
    suggestions: list[EvaluationSuggestion]


class ManualBuildOut(BaseModel):
    id: int
    name: str
    components: list[BuildComponent]
    total_cost: Optional[float]
    last_evaluation: Optional[dict]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ManualBuildSummary(BaseModel):
    id: int
    name: str
    total_cost: Optional[float]
    component_count: int
    updated_at: datetime

    model_config = {"from_attributes": True}
