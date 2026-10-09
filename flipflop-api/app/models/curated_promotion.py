"""
Curated Promotion tracking model.

Tracks dev → production promotions of approved curated playbooks, pricing, 
photo packs, and 3D assets. This ensures Michael's approvals in dev flow to 
production without re-clicking.
"""
from sqlalchemy import Column, Integer, String, Text, JSON, DateTime, Boolean
from datetime import datetime
from app.database import Base


class CuratedPromotion(Base):
    """
    Records each dev → production promotion of the curated FlipFlop set.
    
    A "promotion" exports approved playbooks (with ship_name, display_name, 
    bespoke flags), pricing (sells + upsell deltas), photo-pack refs, and 
    later approved .glb/3D assets from local/dev to production (andromeda-ts).
    
    After promote, only new/changed SKUs go through /approvals again.
    BuildBot/PricingBot/MeshyBot daily updates write to prod admin directly.
    """
    __tablename__ = "curated_promotions"

    id = Column(Integer, primary_key=True, index=True)
    
    # Promotion metadata
    promoted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    promoted_by = Column(String(255), nullable=False)  # Admin user email
    source_environment = Column(String(50), default="dev", nullable=False)
    target_environment = Column(String(50), default="production", nullable=False)
    
    # Promotion content snapshot
    promotion_manifest = Column(JSON, nullable=False)  # Full export payload
    
    # Counts for quick reference
    playbooks_count = Column(Integer, default=0, nullable=False)
    pricing_count = Column(Integer, default=0, nullable=False)
    photo_packs_count = Column(Integer, default=0, nullable=False)
    assets_3d_count = Column(Integer, default=0, nullable=False)
    
    # Status and verification
    status = Column(String(50), default="pending", nullable=False)  # pending/completed/failed/rolled_back
    verification_checks = Column(JSON, nullable=True)  # Pre-promotion safety checks
    
    # Import result
    import_result = Column(JSON, nullable=True)  # Target environment import results
    import_error = Column(Text, nullable=True)  # Error details if import failed
    
    # Rollback tracking
    rolled_back_at = Column(DateTime, nullable=True)
    rolled_back_by = Column(String(255), nullable=True)
    rollback_reason = Column(Text, nullable=True)
    
    # Notes
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
