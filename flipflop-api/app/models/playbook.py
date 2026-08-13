from sqlalchemy import Column, Integer, String, Float, Text, JSON, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
import enum


class PlaybookStatus(enum.Enum):
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class Playbook(Base):
    __tablename__ = "playbooks"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, index=True, nullable=False)
    emoji = Column(String, nullable=True)
    target_budget = Column(Float, nullable=True)
    target_use_case = Column(String, nullable=True)
    target_customer = Column(String, nullable=True)

    specs = Column(JSON, nullable=True)

    historical_demand_pct = Column(Float, default=0.0)
    historical_margin_avg = Column(Float, default=0.0)
    avg_days_to_sell = Column(Float, default=0.0)

    market_selling_price = Column(Float, nullable=True)
    used_market_price = Column(Float, nullable=True)

    # Rich playbook authoring fields (seeded via app/services/playbook_seeder.py)
    what_they_use_it_for = Column(Text, nullable=True)
    what_they_want_from_build = Column(Text, nullable=True)
    critical_success_factors = Column(JSON, nullable=True)
    profit_opportunity_score = Column(Float, nullable=True)
    market_size_score = Column(Float, nullable=True)
    resellability_score = Column(Float, nullable=True)
    liquidity_score = Column(Float, nullable=True)
    risk_score = Column(Float, nullable=True)
    market_growth_direction = Column(String, nullable=True)
    requirements = Column(JSON, nullable=True)
    search_strategy = Column(JSON, nullable=True)
    profit_strategy = Column(JSON, nullable=True)
    ideal_build = Column(JSON, nullable=True)
    seasonality = Column(JSON, nullable=True)
    pricing_model = Column(JSON, nullable=True)
    profit_model = Column(JSON, nullable=True)
    upgrade_strategy = Column(JSON, nullable=True)
    upsell_strategy = Column(JSON, nullable=True)
    component_catalogue = Column(JSON, nullable=True)

    # values_callable stores/queries the Postgres enum by .value ("active") not .name
    # ("ACTIVE"), matching how every query across the codebase filters this column
    # (e.g. `Playbook.status == "active"` in app/main.py, app/api/playbooks.py, etc.)
    status = Column(Enum(PlaybookStatus, values_callable=lambda e: [m.value for m in e]), default=PlaybookStatus.ACTIVE)

    # Commerce & CXP: every ACTIVE playbook must reference exactly one Packaging Playbook (BR-1)
    packaging_playbook_id = Column(Integer, ForeignKey("packaging_playbooks.id"), nullable=True)

    activated_at = Column(DateTime, nullable=True)
    deprecated_at = Column(DateTime, nullable=True)

    # Performance analytics surfaced by PlaybookOut (app/schemas/playbook.py) —
    # populated by outcome-capture/order-reconciliation once builds ship;
    # default to zero/null rather than omitting so API responses never break.
    flip_count = Column(Integer, default=0, nullable=False)
    avg_profit_gbp = Column(Float, nullable=True)
    conversion_rate = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    orders = relationship("Order", back_populates="playbook")


class PlaybookProposal(Base):
    __tablename__ = "playbook_proposals"

    id = Column(Integer, primary_key=True)
    # nullable — a CREATE proposal has no playbook yet; UPDATE/RETIRE require
    # one (enforced in the route, not the schema, per app/api/playbooks.py).
    playbook_id = Column(Integer, ForeignKey("playbooks.id"), index=True, nullable=True)
    action = Column(String, nullable=False)
    status = Column(String, default="pending", nullable=False)
    payload = Column(JSON, nullable=True)

    # Proposal content and resolution — see ProposalCreate/ProposalOut in
    # app/schemas/playbook.py, which every route in app/api/playbooks.py and
    # app/services/playbook_evolution.py already assumes exists.
    proposed_data = Column(JSON, nullable=True)
    reason = Column(Text, nullable=True)
    demand_signals = Column(JSON, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    proposed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    playbook = relationship("Playbook")
