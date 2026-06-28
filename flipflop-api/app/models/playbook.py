from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Playbook(Base):
    """
    A Playbook is a named build strategy — e.g. "Budget Gaming PC" or
    "Office Workstation Flip".  It drives what we search for, how we evaluate
    listings, and what profit structure to expect.

    Status lifecycle:
      candidate  →  active  →  deprecated
                 ↑          ↑
          (approval)   (approval)
    """
    __tablename__ = "playbooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    emoji: Mapped[Optional[str]] = mapped_column(String(8), nullable=True, default="🖥️")

    # Lifecycle
    status: Mapped[str] = mapped_column(String(20), default="candidate")
    # candidate | active | deprecated

    # ── Target use-case ──────────────────────────────────────────────────────
    target_use_case: Mapped[str] = mapped_column(String(100), default="gaming")
    # gaming | office | workstation | budget | ai_workstation | htpc

    # ── Hardware requirements (for listing evaluation) ────────────────────────
    # {
    #   form_factor: "ATX" | "mATX" | "any",
    #   gpu_required: bool,
    #   cpu_min_tier: "i3" | "i5" | "i7" | "i9" | "Ryzen 5" | ...,
    #   ram_min_gb: int,
    #   psu_required: bool,
    #   cooling: "any" | "air" | "aio",
    #   storage_min_gb: int,
    # }
    requirements: Mapped[dict] = mapped_column(JSON, default=dict)

    # ── Case & component catalogue ────────────────────────────────────────────
    # {
    #   preferred_cases: ["Define 7", "NZXT H510", ...],
    #   preferred_coolers: ["be quiet! Pure Rock", ...],
    #   preferred_gpu: ["RTX 3060", "RX 6600", ...],
    #   notes: "Any mid-tower ATX case will do for this build",
    # }
    component_catalogue: Mapped[dict] = mapped_column(JSON, default=dict)

    # ── Search strategy ───────────────────────────────────────────────────────
    # {
    #   keywords: ["gaming pc no gpu", "rtx 3060 desktop", ...],
    #   listing_types: ["buy_it_now", "auction"],
    #   price_min: 80,
    #   price_max: 350,
    #   boost_terms: ["untested", "spares", "no hdd"],
    # }
    search_strategy: Mapped[dict] = mapped_column(JSON, default=dict)

    # ── Upgrade strategy ─────────────────────────────────────────────────────
    # {
    #   required: [{"component": "GPU", "target": "RTX 3060", "max_cost": 90}],
    #   optional: [{"component": "SSD", "target": "500GB NVMe", "max_cost": 25}],
    # }
    upgrade_strategy: Mapped[dict] = mapped_column(JSON, default=dict)

    # ── Profit strategy ───────────────────────────────────────────────────────
    # {
    #   target_margin_pct: 40,
    #   target_profit_gbp: 120,
    #   sell_platform: "eBay",
    #   flip_structure: "buy_upgrade_sell" | "buy_clean_sell" | "bulk_lot",
    #   notes: "List at £350-400 on eBay; local pickup option adds 5-10%",
    # }
    profit_strategy: Mapped[dict] = mapped_column(JSON, default=dict)

    # ── Upsell strategy ───────────────────────────────────────────────────────
    # {
    #   accessories: ["gaming mouse", "gaming keyboard", ...],
    #   note: "Bundle a basic RGB mouse+keyboard set — adds £20-30 to sale price.",
    # }
    upsell_strategy: Mapped[dict] = mapped_column(JSON, default=dict)

    # ── Customer profile ───────────────────────────────────────────────────────
    target_customer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    what_they_use_it_for: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    what_they_want_from_build: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    critical_success_factors: Mapped[list] = mapped_column(JSON, default=list)

    # ── Scores (0-10 floats, updated by evolution engine) ─────────────────────
    profit_opportunity_score: Mapped[float] = mapped_column(Float, default=0.0)
    market_size_score: Mapped[float] = mapped_column(Float, default=0.0)
    resellability_score: Mapped[float] = mapped_column(Float, default=0.0)
    liquidity_score: Mapped[float] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float] = mapped_column(Float, default=5.0)
    composite_rank_score: Mapped[float] = mapped_column(Float, default=0.0)

    # ── Market intelligence ────────────────────────────────────────────────────
    market_growth_direction: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # ── JSON strategy fields ───────────────────────────────────────────────────
    seasonality: Mapped[dict] = mapped_column(JSON, default=dict)
    ideal_build: Mapped[dict] = mapped_column(JSON, default=dict)
    pricing_model: Mapped[dict] = mapped_column(JSON, default=dict)
    profit_model: Mapped[dict] = mapped_column(JSON, default=dict)

    # ── Last reviewed by evolution engine ─────────────────────────────────────
    last_reviewed: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Performance metrics (updated by the evaluator) ────────────────────────
    flip_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_profit_gbp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_days_to_sell: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    conversion_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # conversion_rate = listings matched / listings bought

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deprecated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    proposals: Mapped[list["PlaybookProposal"]] = relationship(
        "PlaybookProposal", back_populates="playbook", cascade="all, delete-orphan"
    )


class PlaybookProposal(Base):
    """
    All playbook mutations go through proposals.  The system (or AI) creates a
    proposal; the user approves or rejects it in the UI before any change lands.

    action:
      CREATE   — brand-new playbook (playbook_id is NULL until approved)
      UPDATE   — modify fields on an existing playbook
      RETIRE   — deprecate an existing playbook

    status:
      pending  →  approved  (changes applied to Playbook row)
                → rejected  (no changes applied)
    """
    __tablename__ = "playbook_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    # CREATE | UPDATE | RETIRE

    playbook_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("playbooks.id", ondelete="SET NULL"), nullable=True
    )

    # Full snapshot of proposed Playbook fields (for CREATE/UPDATE).
    # For RETIRE this is {"status": "deprecated"}.
    proposed_data: Mapped[dict] = mapped_column(JSON, default=dict)

    # Human-readable explanation of why this change is being proposed
    reason: Mapped[str] = mapped_column(Text, default="")

    # Demand signals that triggered this proposal (optional context)
    # e.g. {"trending_category": "Gaming PCs", "demand_strength": "High", "delta_pct": 34}
    demand_signals: Mapped[dict] = mapped_column(JSON, default=dict)

    status: Mapped[str] = mapped_column(String(20), default="pending")
    # pending | approved | rejected

    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    proposed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    playbook: Mapped[Optional["Playbook"]] = relationship(
        "Playbook", back_populates="proposals"
    )
