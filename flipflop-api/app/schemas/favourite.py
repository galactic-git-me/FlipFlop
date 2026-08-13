from datetime import datetime
from pydantic import BaseModel
from typing import Optional


class FavouriteCreate(BaseModel):
    term: Optional[str] = None
    cpk: Optional[str] = None
    category: Optional[str] = None


class FavouriteUpdate(BaseModel):
    term: Optional[str] = None
    cpk: Optional[str] = None
    category: Optional[str] = None


class FavouriteOut(BaseModel):
    id: int
    term: Optional[str]
    cpk: Optional[str]
    category: Optional[str]
    created_at: datetime
    last_matched_at: Optional[datetime]

    model_config = {"from_attributes": True}


class VendorMatrixCell(BaseModel):
    lowest_price: float
    listing_id: str
    url: str
    classification: str


class ProductOption(BaseModel):
    cpk: str
    lowest_price: float
    title: str


class FavouriteMatrixRow(BaseModel):
    query: str
    category: Optional[str] = None
    vendors: dict[str, VendorMatrixCell]
    products: list[ProductOption] = []
