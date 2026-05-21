from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class SourceSearchTermCreate(BaseModel):
    scope: str = "cases"
    group_name: str
    term: str
    source_names: list[str] = Field(default_factory=list)
    attributes: dict = Field(default_factory=dict)
    notes: Optional[str] = None
    enabled: bool = True


class SourceSearchTermUpdate(BaseModel):
    scope: Optional[str] = None
    group_name: Optional[str] = None
    term: Optional[str] = None
    source_names: Optional[list[str]] = None
    attributes: Optional[dict] = None
    notes: Optional[str] = None
    enabled: Optional[bool] = None


class SourceSearchTermOut(SourceSearchTermCreate):
    id: int
    created_at: datetime

    model_config = {"from_attributes": True}
