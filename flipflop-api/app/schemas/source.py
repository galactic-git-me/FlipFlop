from datetime import datetime
from pydantic import BaseModel
from typing import Optional
from app.models.source import SourceType


class DataSourceCreate(BaseModel):
    name: str
    url: str
    source_type: SourceType = SourceType.scrape
    enabled: bool = True
    config: dict = {}


class DataSourceUpdate(BaseModel):
    enabled: Optional[bool] = None
    config: Optional[dict] = None
    url: Optional[str] = None


class DataSourceOut(DataSourceCreate):
    id: int
    listings_found_total: int
    listings_found_last_run: int
    last_scraped_at: Optional[datetime]
    last_error: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
