from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class CustomerReview(Base):
    """Verified customer feedback; only approved 4+ star reviews are public."""

    __tablename__ = "customer_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    manual_build_id: Mapped[int | None] = mapped_column(Integer, index=True)
    customer_id: Mapped[int | None] = mapped_column(Integer, index=True)
    author_name: Mapped[str] = mapped_column(String(200))
    customer_email: Mapped[str | None] = mapped_column(String(320), index=True)
    rating: Mapped[float] = mapped_column(Float)
    review_text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="email")
    source_url: Mapped[str | None] = mapped_column(String(500))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
