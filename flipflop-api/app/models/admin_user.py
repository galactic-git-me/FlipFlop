from sqlalchemy import Boolean, Column, DateTime, Integer, String
from datetime import datetime
from app.database import Base


class AdminUser(Base):
    """Staff account for flipflop-admin. Separate identity space from Customer —
    admin tokens must never be accepted on customer-facing endpoints or vice versa."""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="staff")  # "staff" | "owner"
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
