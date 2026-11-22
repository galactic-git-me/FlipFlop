"""Durable idempotent event ledger shared by autonomous backend agents."""
from datetime import datetime

from sqlalchemy import DateTime, Index, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AgentHandoffEvent(Base):
    __tablename__ = "agent_handoff_events"
    __table_args__ = (
        Index("ix_agent_handoff_events_type_occurred", "event_type", "occurred_at"),
        Index("ix_agent_handoff_events_correlation", "correlation_id"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    schema_version: Mapped[int] = mapped_column(default=1, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64))
    producer: Mapped[str] = mapped_column(String(32))
    occurred_at: Mapped[datetime] = mapped_column(DateTime)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    correlation_id: Mapped[str] = mapped_column(String(64))
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    processing_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
