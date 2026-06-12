from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class GoogleTrendsTimeSeries(Base):
    __tablename__ = "google_trends_timeseries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str] = mapped_column(String(128), index=True)
    date_label: Mapped[str] = mapped_column(String(64))
    value: Mapped[float] = mapped_column(Float)
    collected_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class GoogleTrendsGeo(Base):
    __tablename__ = "google_trends_geo"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str] = mapped_column(String(128))
    region_name: Mapped[str] = mapped_column(String(128))
    region_code: Mapped[str | None] = mapped_column(String(32))
    value: Mapped[float] = mapped_column(Float)
    collected_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class RedditPost(Base):
    __tablename__ = "reddit_posts"
    __table_args__ = (UniqueConstraint("reddit_id", name="uq_reddit_post_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reddit_id: Mapped[str] = mapped_column(String(32), index=True)
    query: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(Text)
    subreddit: Mapped[str] = mapped_column(String(128), index=True)
    post_score: Mapped[int] = mapped_column(Integer, default=0)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    permalink: Mapped[str | None] = mapped_column(Text)
    created_utc: Mapped[datetime] = mapped_column(DateTime, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class SteamHardwareStat(Base):
    __tablename__ = "steam_hardware_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category: Mapped[str] = mapped_column(String(64), index=True)  # GPU | CPU | RAM | OS
    item_name: Mapped[str] = mapped_column(String(255))
    percentage: Mapped[float] = mapped_column(Float)
    change_pct: Mapped[float | None] = mapped_column(Float)
    collected_at: Mapped[datetime] = mapped_column(DateTime, index=True)
