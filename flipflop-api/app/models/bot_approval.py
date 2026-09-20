"""Bot approval queue models for unified admin approval workflow."""
from sqlalchemy import Column, Integer, String, Float, Text, JSON, DateTime, Enum, Boolean
from datetime import datetime
from app.database import Base
import enum


class ApprovalType(enum.Enum):
    """Type of item pending approval."""
    PHOTO_PACK = "photo_pack"           # MeshyBot: 4 reference photos for 3D generation
    MODEL_3D = "model_3d"               # MeshyBot: generated .glb model review
    PLAYBOOK = "playbook"               # BuildBot: curated playbook (core BOM + upsells)
    PREBUILT = "prebuilt"               # BuildBot: pre-built BOM (e.g. Prometheus)
    PRICING = "pricing"                 # PricingBot: price proposal for playbook/prebuilt


class ApprovalStatus(enum.Enum):
    """Approval lifecycle status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DRAFT = "draft"                     # Not yet submitted for approval


class BotApprovalQueue(Base):
    """Unified approval queue for all bot-submitted work."""
    __tablename__ = "bot_approval_queue"

    id = Column(Integer, primary_key=True)
    approval_type = Column(Enum(ApprovalType), nullable=False, index=True)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False, index=True)
    
    # Subject identification
    subject_sku = Column(String(200), nullable=True, index=True)  # For photo packs, 3D models
    subject_category = Column(String(50), nullable=True)  # case/component
    playbook_id = Column(String(100), nullable=True, index=True)  # For playbook/prebuilt/pricing proposals
    
    # Payload (flexible JSON for different approval types)
    payload = Column(JSON, nullable=False)
    # For photo_pack: {sku, category, image_urls: [4 URLs], argb_flags, lighting_zones}
    # For model_3d: {sku, category, glb_url, preview_image_url, poly_count, file_size_kb}
    # For playbook: {playbook_id, customer_type, budget_tier, core_components: [{sku, category, vendor, cost, lead_time}], upsells: [], allowed_cases: []}
    # For prebuilt: {build_id, name, components: [{sku, category, cost}], total_cost}
    # For pricing: {playbook_id, sell_price, total_cost, est_margin, delta_sell_gbp (for upsells), delivery_buffer}
    
    # Pricing fields (for pricing proposals)
    sell_price_gbp = Column(Float, nullable=True)
    total_cost_gbp = Column(Float, nullable=True)
    est_margin_pct = Column(Float, nullable=True)
    
    # Metadata
    submitted_by = Column(String(100), nullable=True)  # Bot identifier
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_by = Column(String(100), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PlaybookProposalExtended(Base):
    """Extended playbook proposal table for BuildBot submissions."""
    __tablename__ = "playbook_proposals_extended"
    
    id = Column(Integer, primary_key=True)
    playbook_id = Column(String(100), nullable=False, index=True)
    customer_type = Column(String(100), nullable=True)
    budget_tier = Column(String(50), nullable=True)  # Value/Balanced/Performance
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.DRAFT, nullable=False)
    
    # Core components BOM
    core_components = Column(JSON, nullable=False)
    # [{sku, category, vendor, title, cost_gbp, lead_time_days, argb_flags}]
    
    # Upsells
    upsells = Column(JSON, nullable=True)
    # [{category, from_sku, to_sku, delta_cost_gbp, delta_sell_gbp, reason}]
    
    # Allowed cases
    allowed_cases = Column(JSON, nullable=True)
    # [sku1, sku2, ...]
    
    # Pricing (may be empty until PricingBot fills it)
    sell_price_gbp = Column(Float, nullable=True)
    total_cost_gbp = Column(Float, nullable=True)
    est_margin_pct = Column(Float, nullable=True)
    
    # Metadata
    submitted_by = Column(String(100), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PricingProposal(Base):
    """Pricing proposals from PricingBot."""
    __tablename__ = "pricing_proposals"
    
    id = Column(Integer, primary_key=True)
    target_type = Column(String(50), nullable=False)  # playbook / prebuilt
    target_id = Column(String(100), nullable=False, index=True)  # playbook_id or build_id
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False)
    
    # Pricing details
    sell_price_gbp = Column(Float, nullable=False)
    total_cost_gbp = Column(Float, nullable=False)
    est_margin_pct = Column(Float, nullable=False)
    delivery_buffer_gbp = Column(Float, nullable=True)  # Free delivery buffer (£50-£100)
    
    # Upsell pricing (if applicable)
    upsell_delta_sell_gbp = Column(Float, nullable=True)
    upsell_delta_cost_gbp = Column(Float, nullable=True)
    
    # Justification
    pricing_rationale = Column(Text, nullable=True)
    market_comparison = Column(JSON, nullable=True)  # Competitor prices, market data
    
    # Metadata
    submitted_by = Column(String(100), nullable=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
