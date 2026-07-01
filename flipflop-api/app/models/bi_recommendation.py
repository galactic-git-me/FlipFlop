from sqlalchemy import Column, Integer, Float, Text, DateTime, Enum, JSON
from datetime import datetime
from app.database import Base
import enum


class BiCategory(enum.Enum):
    PROFITABILITY = "profitability"
    CLV = "clv"
    UPGRADE_CONVERSION = "upgrade_conversion"
    PACKAGING_COST = "packaging_cost"
    SUPPLIER_PERFORMANCE = "supplier_performance"
    REPEAT_PURCHASE = "repeat_purchase"
    REVIEW_SENTIMENT = "review_sentiment"
    INVENTORY = "inventory"


class BiRecommendationStatus(enum.Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    ACTIONED = "actioned"
    DISMISSED = "dismissed"


class BiRecommendation(Base):
    """AI-generated business intelligence recommendation. PRD Ch.6.10, Ch.17. Advisory only (CBR-9)."""
    __tablename__ = "bi_recommendations"

    id = Column(Integer, primary_key=True)
    category = Column(Enum(BiCategory), nullable=False)
    summary = Column(Text, nullable=False)
    supporting_data_json = Column(JSON, nullable=True)
    confidence = Column(Float, nullable=True)
    status = Column(Enum(BiRecommendationStatus), default=BiRecommendationStatus.NEW, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
