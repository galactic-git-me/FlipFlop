"""Versioned contracts shared by the autonomous demand, pricing and Playbook workers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


AgentEventType = Literal[
    "demand_signal_batch_ready",
    "component_market_price_changed",
    "pricing_snapshot_completed",
    "playbook_refresh_requested",
    "playbook_refresh_completed",
    "agent_run_blocked",
]


class AgentEvent(BaseModel):
    """A validated, idempotent handoff; evidence references point to durable source records."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: AgentEventType
    producer: Literal["demand", "pricing", "playbook", "system"]
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: str = Field(min_length=1, max_length=255)
    correlation_id: str = Field(default_factory=lambda: str(uuid4()), max_length=64)
    evidence_refs: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


class PriceChangePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: str
    condition: Literal["new", "used", "refurbished"]
    geography: str = "GB"
    market_kind: Literal["active", "sold"]
    previous_median_gbp: str
    current_median_gbp: str
    change_percent: str
    evidence: dict[str, Any]


class DemandBatchPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_id: str
    sources: list[str] = Field(default_factory=list)
    observation_count: int = Field(ge=0)
    completed_at: datetime


class PlaybookRefreshPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trigger: str
    scope: str = "all_segments"
    demand_event_ids: list[str] = Field(default_factory=list)
    price_event_ids: list[str] = Field(default_factory=list)
    extension_batch_id: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
