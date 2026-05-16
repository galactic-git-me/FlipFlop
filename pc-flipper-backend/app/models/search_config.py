from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SearchConfig(Base):
    __tablename__ = "search_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="default")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    min_price: Mapped[float] = mapped_column(Float, default=0)
    max_price: Mapped[float] = mapped_column(Float, default=150)
    conditions: Mapped[list] = mapped_column(JSON, default=lambda: ["used"])
    cpu_types: Mapped[list] = mapped_column(JSON, default=list)
    ram_min_gb: Mapped[int] = mapped_column(Integer, default=8)
    ram_types: Mapped[list] = mapped_column(JSON, default=lambda: ["DDR4"])
    require_storage: Mapped[bool] = mapped_column(Boolean, default=False)
    require_gpu: Mapped[bool] = mapped_column(Boolean, default=False)
    keywords: Mapped[list] = mapped_column(JSON, default=lambda: [
        "desktop pc",
        "preowned desktop",
        "pre owned workstation",
        "refurbished workstation",
        "refurbished desktop pc",
        "gaming pc tower",
        "motherboard bundle",
        "used cpu",
        "used gpu",
        "ddr4 ram lot",
    ])
    exclude_keywords: Mapped[list] = mapped_column(JSON, default=list)
    gem_keywords: Mapped[list] = mapped_column(JSON, default=lambda: [
        "no hdd", "untested", "collection only", "for parts",
        "no gpu", "spares", "no hard drive", "poor condition",
    ])
    intent: Mapped[str] = mapped_column(String(50), default="flip_gaming")

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
