import enum
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, Text, Enum, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SourceType(str, enum.Enum):
    api = "api"
    scrape = "scrape"


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    url: Mapped[str] = mapped_column(String(1000))
    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), default=SourceType.scrape)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Scraper config — search URL template, selectors, etc.
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    # Stats
    listings_found_total: Mapped[int] = mapped_column(Integer, default=0)
    listings_found_last_run: Mapped[int] = mapped_column(Integer, default=0)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<DataSource {self.id} {self.name!r} enabled={self.enabled}>"
