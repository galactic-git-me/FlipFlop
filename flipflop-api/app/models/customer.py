from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    address = Column(String(500), nullable=True)
    phone = Column(String(20), nullable=True)
    last_login = Column(DateTime, nullable=True)

    # OAuth fields
    google_id = Column(String(255), unique=True, nullable=True, index=True)
    google_email = Column(String(255), nullable=True)
    github_id = Column(Integer, unique=True, nullable=True, index=True)
    github_username = Column(String(255), nullable=True)
    oauth_provider = Column(String(50), nullable=True)  # 'google', 'github', or null for email

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
