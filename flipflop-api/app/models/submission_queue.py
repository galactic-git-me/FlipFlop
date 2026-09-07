from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from datetime import datetime
from .base import BaseModel

class SubmissionQueue(BaseModel):
    __tablename__ = "submission_queue"

    id = Column(Integer, primary_key=True)

    # Queue status
    status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed

    # Submission data
    search_run_id = Column(String(255), nullable=False)
    search_id = Column(String(255), nullable=False)
    query = Column(String(500), nullable=False)
    source_url = Column(String(1000), nullable=False)
    max_candidates_for_deep_research = Column(Integer, default=50)

    # Listings data (stored as JSON)
    listings_json = Column(JSON, nullable=False)

    # Durable progress used by the API process when the queue worker is
    # running separately from it.  This is incremented only for listings that
    # pass the scan's cross-run dedupe check.
    ingested_new_count = Column(Integer, default=0, nullable=False)

    # Retry tracking
    retry_count = Column(Integer, default=0)
    last_error = Column(Text, nullable=True)

    # Processing timestamps
    first_attempt_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_attempt_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
