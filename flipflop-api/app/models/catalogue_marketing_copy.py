from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CatalogueMarketingCopy(Base):
    __tablename__ = "catalogue_marketing_copy"
    __table_args__ = (
        UniqueConstraint("subject_type", "subject_id", "context_key", name="uq_catalogue_marketing_copy_subject_context"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    context_key: Mapped[str] = mapped_column(String(255), nullable=False, default="product")
    copy: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model: Mapped[str] = mapped_column(String(160), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
