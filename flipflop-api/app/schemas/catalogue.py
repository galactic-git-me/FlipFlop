from typing import Optional
from pydantic import BaseModel, Field


# ── PlaybookSlot ──────────────────────────────────────────────────────────────

class PlaybookSlotBase(BaseModel):
    slot_type: str
    is_customer_visible: bool = True
    tier_names: dict = Field(default_factory=lambda: {"budget": "Budget", "mid": "Mid-Range", "high": "High End"})
    score_band_budget: list[int] = Field(default_factory=lambda: [40, 65])
    score_band_mid: list[int] = Field(default_factory=lambda: [65, 80])
    score_band_high: list[int] = Field(default_factory=lambda: [80, 100])


class PlaybookSlotUpdate(BaseModel):
    is_customer_visible: Optional[bool] = None
    tier_names: Optional[dict] = None
    score_band_budget: Optional[list[int]] = None
    score_band_mid: Optional[list[int]] = None
    score_band_high: Optional[list[int]] = None


class PlaybookSlotOut(PlaybookSlotBase):
    id: int
    playbook_id: int
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}


# ── CatalogueVariant ──────────────────────────────────────────────────────────

class CatalogueVariantOut(BaseModel):
    id: int
    listing_id: int
    slot_id: int
    status: str
    display_price: float
    tier: str
    consecutive_misses: int
    last_seen_at: str
    auto_published_at: str
    reviewed_at: Optional[str]
    reviewed_by: Optional[str]
    reject_reason: Optional[str]

    model_config = {"from_attributes": True}


class RejectBody(BaseModel):
    reason: str


# ── CaseCatalogue ─────────────────────────────────────────────────────────────

class CaseCatalogueCreate(BaseModel):
    name: str
    brand: str
    form_factor: str
    images: list[str] = Field(default_factory=list)
    rrp_gbp: float
    is_transparent_panel: bool = True
    notes: Optional[str] = None


class CaseCatalogueUpdate(BaseModel):
    name: Optional[str] = None
    brand: Optional[str] = None
    form_factor: Optional[str] = None
    images: Optional[list[str]] = None
    rrp_gbp: Optional[float] = None
    is_transparent_panel: Optional[bool] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class CaseCatalogueOut(BaseModel):
    id: int
    name: str
    brand: str
    form_factor: str
    images: list[str]
    rrp_gbp: float
    is_transparent_panel: bool
    status: str
    notes: Optional[str]
    created_at: str
    updated_at: str

    model_config = {"from_attributes": True}
