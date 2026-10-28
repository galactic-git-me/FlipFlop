from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CustomBuildSettings(Base):
    __tablename__ = "custom_build_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    is_live: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
