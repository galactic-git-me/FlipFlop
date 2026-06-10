from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, field_validator


# ─── Playbook schemas ──────────────────────────────────────────────────────────

class PlaybookBase(BaseModel):
    name: str
    description: Optional[str] = None
    emoji: Optional[str] = "🖥️"
    target_use_case: str = "gaming"
    requirements: dict[str, Any] = {}
    component_catalogue: dict[str, Any] = {}
    search_strategy: dict[str, Any] = {}
    upgrade_strategy: dict[str, Any] = {}
    profit_strategy: dict[str, Any] = {}

    # Customer profile
    target_customer: Optional[str] = None
    what_they_use_it_for: Optional[str] = None
    what_they_want_from_build: Optional[str] = None
    critical_success_factors: list[str] = []

    # Scores
    profit_opportunity_score: float = 0.0
    market_size_score: float = 0.0
    resellability_score: float = 0.0
    liquidity_score: float = 0.0
    risk_score: float = 5.0
    composite_rank_score: float = 0.0
    market_growth_direction: Optional[str] = None

    # Intelligence
    seasonality: dict[str, Any] = {}
    ideal_build: dict[str, Any] = {}
    pricing_model: dict[str, Any] = {}
    profit_model: dict[str, Any] = {}


class PlaybookCreate(PlaybookBase):
    status: str = "candidate"


class PlaybookUpdate(BaseModel):
    """All fields optional for PATCH-style updates."""
    name: Optional[str] = None
    description: Optional[str] = None
    emoji: Optional[str] = None
    target_use_case: Optional[str] = None
    requirements: Optional[dict[str, Any]] = None
    component_catalogue: Optional[dict[str, Any]] = None
    search_strategy: Optional[dict[str, Any]] = None
    upgrade_strategy: Optional[dict[str, Any]] = None
    profit_strategy: Optional[dict[str, Any]] = None
    status: Optional[str] = None


class PlaybookOut(PlaybookBase):
    id: int
    status: str
    flip_count: int
    avg_profit_gbp: Optional[float]
    avg_days_to_sell: Optional[float]
    conversion_rate: Optional[float]
    created_at: datetime
    updated_at: datetime
    activated_at: Optional[datetime]
    deprecated_at: Optional[datetime]
    last_reviewed: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── Proposal schemas ─────────────────────────────────────────────────────────

class ProposalCreate(BaseModel):
    action: str  # CREATE | UPDATE | RETIRE
    playbook_id: Optional[int] = None
    proposed_data: dict[str, Any] = {}
    reason: str = ""
    demand_signals: dict[str, Any] = {}

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"CREATE", "UPDATE", "RETIRE"}
        if v.upper() not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v.upper()


class ProposalResolve(BaseModel):
    approved: bool
    rejection_reason: Optional[str] = None
    resolved_by: Optional[str] = "user"


class ProposalOut(BaseModel):
    id: int
    action: str
    playbook_id: Optional[int]
    proposed_data: dict[str, Any]
    reason: str
    demand_signals: dict[str, Any]
    status: str
    rejection_reason: Optional[str]
    proposed_at: datetime
    resolved_at: Optional[datetime]
    resolved_by: Optional[str]

    # Embedded playbook snapshot (name only, for UI display)
    playbook_name: Optional[str] = None

    model_config = {"from_attributes": True}
