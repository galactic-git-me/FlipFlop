from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
from app.services.license_key_crypto import decrypt_license_key, encrypt_license_key


class EncryptedLicenseKey(TypeDecorator):
    impl = String(255)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return encrypt_license_key(value)

    def process_result_value(self, value, dialect):
        return decrypt_license_key(value)


class OSComponent(Base):
    __tablename__ = "os_components"

    id = Column(Integer, primary_key=True)
    os_type = Column(String(50), nullable=False, index=True)  # windows_home, windows_pro, linux_ubuntu, etc
    license_key = Column(EncryptedLicenseKey(), nullable=False)
    assigned_to_order_id = Column(Integer, ForeignKey('orders.id'), nullable=True)
    purchased_cost = Column(Float, nullable=False)
    resale_price = Column(Float, nullable=False)
    status = Column(String(50), default='available', index=True)  # available, assigned, used

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    assigned_order = relationship("Order", back_populates="os_component", foreign_keys=[assigned_to_order_id])
