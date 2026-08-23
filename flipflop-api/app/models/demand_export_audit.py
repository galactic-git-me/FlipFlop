"""Demand Export Audit model for Phase 3 F3.1.

Audit trail for CSV exports of demand metrics.
Tracks what was exported, when, and by whom.
"""

from datetime import datetime
from sqlalchemy import String, Integer, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DemandExportAudit(Base):
    __tablename__ = "demand_export_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(Integer)

    export_type: Mapped[str] = mapped_column(String(30))
    filter_params: Mapped[dict] = mapped_column(JSON, default=dict)

    row_count: Mapped[int] = mapped_column(Integer)
    exported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
