from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class SearchConfigUpdate(BaseModel):
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    conditions: Optional[list[str]] = None
    cpu_types: Optional[list[str]] = None
    ram_min_gb: Optional[int] = None
    ram_types: Optional[list[str]] = None
    require_storage: Optional[bool] = None
    require_gpu: Optional[bool] = None
    keywords: Optional[list[str]] = None
    exclude_keywords: Optional[list[str]] = None
    gem_keywords: Optional[list[str]] = None
    intent: Optional[str] = None


class SearchConfigOut(BaseModel):
    id: int
    name: str
    is_active: bool
    min_price: float
    max_price: float
    conditions: list[str]
    cpu_types: list[str]
    ram_min_gb: int
    ram_types: list[str]
    require_storage: bool
    require_gpu: bool
    keywords: list[str]
    exclude_keywords: list[str]
    gem_keywords: list[str]
    intent: str
    updated_at: datetime

    model_config = {"from_attributes": True}
