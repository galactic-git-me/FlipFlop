"""Single-row flag set by FlipFlopXtension's /scan-sweep-complete call once
a whole scan sweep (every enabled search, every marketplace) has finished
scraping and issuing its (queued, fire-and-forget) submissions. The queue
processor's _phase2_trigger_loop (app/workers/queue_processor.py) polls this
and only runs Phase 2 classification once BOTH this is pending AND the
submission_queue has actually drained — the signal alone doesn't guarantee
every queued submission has been processed yet."""
from datetime import datetime
from sqlalchemy import Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class GemRadarSweepSignal(Base):
    __tablename__ = "gem_radar_sweep_signal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    requested_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self):
        return f"<GemRadarSweepSignal pending={self.pending} requested_at={self.requested_at}>"
