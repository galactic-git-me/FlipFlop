"""One row per search-term scan run (FlipFlopXtension's runScan()), recorded
alongside the extension's local scan-history CSV so the admin Sourcing
Dashboard can show the same audit trail without reading a file from the
user's Downloads folder.
"""
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarScanRun(Base):
    __tablename__ = "gem_radar_scan_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    search_term: Mapped[str] = mapped_column(String(400), index=True)
    total_listings_found: Mapped[int] = mapped_column(Integer, default=0)
    vendors: Mapped[list[str]] = mapped_column(JSON, default=list)
    run_by: Mapped[str] = mapped_column(String(20), default="Automatic")  # "Manual" | "Automatic"
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<GemRadarScanRun {self.search_term!r} {self.total_listings_found} listings @{self.occurred_at}>"
