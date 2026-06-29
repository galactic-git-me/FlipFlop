from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class DesktopTheme(Base):
    __tablename__ = "desktop_themes"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False, index=True)  # Cyberpunk Blue, Forest Green, etc
    rainmeter_config_path = Column(String(500), nullable=False)
    desktop_background_path = Column(String(500), nullable=False)
    preview_image_path = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    orders = relationship("Order", back_populates="theme")
