from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    # OAuth-created customers do not have a local password. Email/password
    # accounts still populate this field through auth_service.
    password_hash = Column(String(255), nullable=True)
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

    # Registration data (Michael + AnalyticsBot requirements)
    year_of_birth = Column(Integer, nullable=True)  # For age band + birthday offers
    marketing_opt_in = Column(Boolean, default=False, nullable=False)  # Separate from account creation
    acquisition_source = Column(String(50), nullable=True)  # search/youtube/reddit/referral/ebay/other
    acquisition_detail = Column(String(255), nullable=True)  # e.g., specific referral code
    
    # Customer profile preferences (for better personalization)
    profile_metadata = Column(JSON, nullable=True)  # Extensible JSON for additional profile data
    
    # Magic link support (for passwordless auth)
    magic_link_token = Column(String(255), nullable=True, index=True)
    magic_link_expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
