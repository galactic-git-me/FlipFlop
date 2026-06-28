# Playbook Evolution System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Build an autonomous playbook evolution system that continuously identifies, optimises, ranks, and retires PC build opportunities based on real-world demand, sourcing, resale values and profitability.

**Architecture:** Extend the existing `Playbook` model with rich strategy fields (scores, seasonality, ideal build, customer profile). A rewritten 9-phase daily evolution engine scores each playbook on market size, liquidity, resellability, risk and profit. A new frontend dashboard shows rankings, seasonality graphs, build costs and profit ranges.

**Tech Stack:** FastAPI + SQLAlchemy async (PostgreSQL), Alembic migrations, Next.js 15, Tailwind CSS, Recharts for seasonality graphs, existing eBay pricing + demand services.

---

### Task 1: DB Migration — Extend Playbook model with new fields

**Files:**
- Modify: `pc-flipper-backend/app/models/playbook.py`
- Create: `pc-flipper-backend/alembic/versions/20260610_0006_playbook_evolution_fields.py`

- [ ] **Step 1: Add new columns to `Playbook` model**

In `pc-flipper-backend/app/models/playbook.py`, add after the `upsell_strategy` column:

```python
# ── Customer profile (new spec fields) ────────────────────────────────────────
target_customer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
what_they_use_it_for: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
what_they_want_from_build: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
critical_success_factors: Mapped[list] = mapped_column(JSON, default=list)

# ── Scores (0-10 floats, updated by evolution engine) ─────────────────────────
profit_opportunity_score: Mapped[float] = mapped_column(Float, default=0.0)
market_size_score: Mapped[float] = mapped_column(Float, default=0.0)
resellability_score: Mapped[float] = mapped_column(Float, default=0.0)
liquidity_score: Mapped[float] = mapped_column(Float, default=0.0)
risk_score: Mapped[float] = mapped_column(Float, default=5.0)
composite_rank_score: Mapped[float] = mapped_column(Float, default=0.0)

# ── Market intelligence ────────────────────────────────────────────────────────
market_growth_direction: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
# "Growing" | "Stable" | "Shrinking"

# ── Seasonality: {jan:0..10, ..., dec:0..10, peak_months:[], slow_months:[],
#                 current_position:"", days_until_peak:0} ─────────────────────
seasonality: Mapped[dict] = mapped_column(JSON, default=dict)

# ── Ideal build: {cpu:{candidate_models:[], target_price:0, walk_away_price:0,
#    search_terms:[], negative_search_terms:[]}, gpu:{...}, ...} ───────────────
ideal_build: Mapped[dict] = mapped_column(JSON, default=dict)

# ── Pricing model: {minimum_build_cost:0, expected_build_cost:0,
#                   maximum_build_cost:0} ─────────────────────────────────────
pricing_model: Mapped[dict] = mapped_column(JSON, default=dict)

# ── Profit model: {minimum_profit:0, expected_profit:0, maximum_profit:0,
#                  expected_roi_pct:0} ─────────────────────────────────────────
profit_model: Mapped[dict] = mapped_column(JSON, default=dict)

# ── Last reviewed by evolution engine ─────────────────────────────────────────
last_reviewed: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
```

- [ ] **Step 2: Create Alembic migration**

Create `pc-flipper-backend/alembic/versions/20260610_0006_playbook_evolution_fields.py`:

```python
"""Add playbook evolution fields (scores, seasonality, ideal_build, pricing/profit models).

Revision ID: 20260610_0006
Revises: 20260603_0005
Create Date: 2026-06-10 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = "20260610_0006"
down_revision = "20260603_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("playbooks", sa.Column("target_customer", sa.String(200), nullable=True))
    op.add_column("playbooks", sa.Column("what_they_use_it_for", sa.Text, nullable=True))
    op.add_column("playbooks", sa.Column("what_they_want_from_build", sa.Text, nullable=True))
    op.add_column("playbooks", sa.Column("critical_success_factors", sa.JSON, nullable=True, server_default="[]"))
    op.add_column("playbooks", sa.Column("profit_opportunity_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("market_size_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("resellability_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("liquidity_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("risk_score", sa.Float, nullable=False, server_default="5"))
    op.add_column("playbooks", sa.Column("composite_rank_score", sa.Float, nullable=False, server_default="0"))
    op.add_column("playbooks", sa.Column("market_growth_direction", sa.String(20), nullable=True))
    op.add_column("playbooks", sa.Column("seasonality", sa.JSON, nullable=True, server_default="{}"))
    op.add_column("playbooks", sa.Column("ideal_build", sa.JSON, nullable=True, server_default="{}"))
    op.add_column("playbooks", sa.Column("pricing_model", sa.JSON, nullable=True, server_default="{}"))
    op.add_column("playbooks", sa.Column("profit_model", sa.JSON, nullable=True, server_default="{}"))
    op.add_column("playbooks", sa.Column("last_reviewed", sa.DateTime, nullable=True))


def downgrade() -> None:
    for col in ["target_customer", "what_they_use_it_for", "what_they_want_from_build",
                "critical_success_factors", "profit_opportunity_score", "market_size_score",
                "resellability_score", "liquidity_score", "risk_score", "composite_rank_score",
                "market_growth_direction", "seasonality", "ideal_build", "pricing_model",
                "profit_model", "last_reviewed"]:
        op.drop_column("playbooks", col)
```

- [ ] **Step 3: Apply migration inside running backend container**

```bash
docker exec flipflop-backend alembic upgrade head
```
Expected: `Running upgrade 20260603_0005 -> 20260610_0006`

- [ ] **Step 4: Commit**

```bash
git add pc-flipper-backend/app/models/playbook.py pc-flipper-backend/alembic/versions/20260610_0006_playbook_evolution_fields.py
git commit -m "feat: extend Playbook model with evolution fields (scores, seasonality, ideal_build)"
```

---

### Task 2: Update Pydantic Schemas + API

**Files:**
- Modify: `pc-flipper-backend/app/schemas/playbook.py`
- Modify: `pc-flipper-backend/app/api/playbooks.py` (add `/seed` and `/ranked` endpoints)

- [ ] **Step 1: Extend `PlaybookBase` in schemas**

Replace the `PlaybookBase` class in `pc-flipper-backend/app/schemas/playbook.py`:

```python
class PlaybookBase(BaseModel):
    name: str
    description: Optional[str] = None
    emoji: Optional[str] = "🖥️"
    target_use_case: str = "gaming"
    target_customer: Optional[str] = None
    what_they_use_it_for: Optional[str] = None
    what_they_want_from_build: Optional[str] = None
    critical_success_factors: list[str] = []
    requirements: dict[str, Any] = {}
    component_catalogue: dict[str, Any] = {}
    search_strategy: dict[str, Any] = {}
    upgrade_strategy: dict[str, Any] = {}
    profit_strategy: dict[str, Any] = {}
    upsell_strategy: dict[str, Any] = {}
    # Scores
    profit_opportunity_score: float = 0.0
    market_size_score: float = 0.0
    resellability_score: float = 0.0
    liquidity_score: float = 0.0
    risk_score: float = 5.0
    composite_rank_score: float = 0.0
    market_growth_direction: Optional[str] = None
    # Intelligence
    seasonality: dict[str, Any] = {}
    ideal_build: dict[str, Any] = {}
    pricing_model: dict[str, Any] = {}
    profit_model: dict[str, Any] = {}
```

Replace `PlaybookOut` to include new fields + `last_reviewed`:

```python
class PlaybookOut(PlaybookBase):
    id: int
    status: str
    flip_count: int
    avg_profit_gbp: Optional[float]
    avg_days_to_sell: Optional[float]
    conversion_rate: Optional[float]
    last_reviewed: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    activated_at: Optional[datetime]
    deprecated_at: Optional[datetime]

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Add `/seed` endpoint to `pc-flipper-backend/app/api/playbooks.py`**

Add after the `list_playbooks` endpoint:

```python
@router.post("/seed", status_code=201)
async def seed_initial_playbooks(db: AsyncSession = Depends(get_db)):
    """Create the 10 canonical starting playbooks if they don't already exist."""
    from app.services.playbook_seeder import seed_playbooks
    created = await seed_playbooks(db)
    return {"ok": True, "created": created}
```

Add a `/ranked` endpoint:

```python
@router.get("/ranked", response_model=list[PlaybookOut])
async def list_playbooks_ranked(db: AsyncSession = Depends(get_db)):
    """Return active playbooks sorted by composite_rank_score descending."""
    result = await db.execute(
        select(Playbook)
        .where(Playbook.status == "active")
        .order_by(Playbook.composite_rank_score.desc())
    )
    return result.scalars().all()
```

- [ ] **Step 3: Commit**

```bash
git add pc-flipper-backend/app/schemas/playbook.py pc-flipper-backend/app/api/playbooks.py
git commit -m "feat: extend playbook schemas and add /seed + /ranked API endpoints"
git push origin master
```

---

### Task 3: Seed 10 Initial Playbooks

**Files:**
- Create: `pc-flipper-backend/app/services/playbook_seeder.py`

- [ ] **Step 1: Create seeder service**

Create `pc-flipper-backend/app/services/playbook_seeder.py` with full initial playbook data:

```python
"""
Playbook Seeder — creates the 10 canonical starting playbooks.
Safe to run multiple times (skips existing by name).
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.playbook import Playbook

_INITIAL_PLAYBOOKS = [
    {
        "name": "Budget Gamer",
        "emoji": "🎮",
        "status": "active",
        "target_use_case": "gaming",
        "target_customer": "Kids / Teens",
        "what_they_use_it_for": "Fortnite, Minecraft, Roblox, Valorant, Discord, streaming",
        "what_they_want_from_build": "Something that runs games at 1080p. Budget matters more than specs.",
        "critical_success_factors": ["Price under £350", "Runs AAA titles at 1080p", "GPU present", "Reliable brand"],
        "profit_opportunity_score": 5.0,
        "market_size_score": 8.0,
        "resellability_score": 8.0,
        "liquidity_score": 9.0,
        "risk_score": 3.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 16, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["gaming pc no gpu", "gaming pc rtx 3060", "gaming pc gtx 1660", "budget gaming desktop"],
            "price_min": 80, "price_max": 250, "listing_types": ["buy_it_now", "auction"]
        },
        "profit_strategy": {"target_profit_gbp": 100, "target_margin_pct": 40, "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell"},
        "ideal_build": {
            "cpu": {"candidate_models": ["Ryzen 5 5600", "i5-10400F", "i5-12400F"], "target_price": 50, "walk_away_price": 80,
                    "search_terms": ["ryzen 5 5600", "i5 10400f", "i5 12400f"], "negative_search_terms": ["faulty", "broken", "for parts"]},
            "gpu": {"candidate_models": ["RTX 3060", "RTX 3060 Ti", "RX 6600 XT"], "target_price": 90, "walk_away_price": 130,
                    "search_terms": ["rtx 3060", "rx 6600"], "negative_search_terms": ["faulty", "mining", "blower"]},
            "ram": {"candidate_models": ["16GB DDR4 3200MHz"], "target_price": 20, "walk_away_price": 35,
                    "search_terms": ["16gb ddr4 ram", "ddr4 3200"], "negative_search_terms": ["faulty", "untested"]},
            "storage": {"candidate_models": ["500GB NVMe SSD", "1TB NVMe SSD"], "target_price": 25, "walk_away_price": 45,
                        "search_terms": ["nvme ssd 500gb", "m.2 ssd 1tb"], "negative_search_terms": []},
            "psu": {"candidate_models": ["550W 80+ Bronze", "650W 80+ Bronze"], "target_price": 25, "walk_away_price": 45,
                    "search_terms": ["550w psu", "650w power supply"], "negative_search_terms": ["faulty", "no cable"]},
        },
        "seasonality": {"jan": 4, "feb": 3, "mar": 4, "apr": 4, "may": 5, "jun": 5, "jul": 5, "aug": 6,
                        "sep": 6, "oct": 7, "nov": 9, "dec": 10,
                        "peak_months": ["november", "december"], "slow_months": ["january", "february"],
                        "current_position": "approaching_peak", "days_until_peak": 150},
    },
    {
        "name": "Mainstream Gamer",
        "emoji": "🖥️",
        "status": "active",
        "target_use_case": "gaming",
        "target_customer": "Most Buyers",
        "what_they_use_it_for": "1440p gaming, streaming, modern AAA titles, content consumption",
        "what_they_want_from_build": "Solid 1440p performance, reliable brand, looks decent, good price-to-performance",
        "critical_success_factors": ["1440p capable GPU", "Ryzen 5000/Intel 12th+ CPU", "16-32GB RAM", "NVMe storage"],
        "profit_opportunity_score": 5.0,
        "market_size_score": 9.0,
        "resellability_score": 9.0,
        "liquidity_score": 8.0,
        "risk_score": 3.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 16, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["gaming pc rtx 3070", "gaming pc rtx 3080", "gaming pc rx 6700", "custom gaming pc"],
            "price_min": 150, "price_max": 400, "listing_types": ["buy_it_now", "auction"]
        },
        "profit_strategy": {"target_profit_gbp": 140, "target_margin_pct": 38, "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell"},
        "ideal_build": {
            "cpu": {"candidate_models": ["Ryzen 5 5600X", "Ryzen 7 5700X", "i5-12600K", "i5-13600K"], "target_price": 70, "walk_away_price": 110,
                    "search_terms": ["ryzen 7 5700x", "i5 12600k", "i5 13600k"], "negative_search_terms": ["faulty", "for parts"]},
            "gpu": {"candidate_models": ["RTX 3070", "RTX 3070 Ti", "RX 6700 XT", "RTX 4060 Ti"], "target_price": 140, "walk_away_price": 200,
                    "search_terms": ["rtx 3070", "rx 6700 xt", "rtx 4060 ti"], "negative_search_terms": ["mining", "faulty", "blower"]},
            "ram": {"candidate_models": ["32GB DDR4 3200MHz", "16GB DDR4 3600MHz"], "target_price": 30, "walk_away_price": 55,
                    "search_terms": ["32gb ddr4", "16gb ddr4 3600"], "negative_search_terms": []},
            "storage": {"candidate_models": ["1TB NVMe SSD"], "target_price": 35, "walk_away_price": 60,
                        "search_terms": ["1tb nvme ssd", "samsung 970 evo"], "negative_search_terms": []},
            "psu": {"candidate_models": ["650W 80+ Gold", "750W 80+ Gold"], "target_price": 40, "walk_away_price": 70,
                    "search_terms": ["650w gold psu", "750w modular psu"], "negative_search_terms": ["faulty"]},
        },
        "seasonality": {"jan": 5, "feb": 5, "mar": 6, "apr": 6, "may": 7, "jun": 7, "jul": 7, "aug": 7,
                        "sep": 7, "oct": 8, "nov": 10, "dec": 9,
                        "peak_months": ["october", "november"], "slow_months": ["january", "february"],
                        "current_position": "mid_season", "days_until_peak": 120},
    },
    {
        "name": "RGB Showcase Build",
        "emoji": "🌈",
        "status": "active",
        "target_use_case": "gaming",
        "target_customer": "Impulse Buyers",
        "what_they_use_it_for": "Gaming, TikTok content, desk aesthetics, RGB lighting displays",
        "what_they_want_from_build": "Looks expensive, RGB everywhere, white aesthetic or black theme, fish tank case",
        "critical_success_factors": ["Tempered glass case", "RGB lighting", "White/black theme consistency", "Cable management", "Visually striking"],
        "profit_opportunity_score": 5.0,
        "market_size_score": 7.0,
        "resellability_score": 8.0,
        "liquidity_score": 7.0,
        "risk_score": 4.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "Ryzen 5", "ram_min_gb": 16, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["white gaming pc", "rgb gaming pc", "gaming pc rgb", "showcase gaming pc build"],
            "price_min": 100, "price_max": 350, "listing_types": ["buy_it_now", "auction"]
        },
        "profit_strategy": {"target_profit_gbp": 130, "target_margin_pct": 42, "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
                             "notes": "Presentation is everything. Good photos = 15-20% higher final price."},
        "ideal_build": {
            "cpu": {"candidate_models": ["Ryzen 5 5600", "Ryzen 7 5700X"], "target_price": 55, "walk_away_price": 85,
                    "search_terms": ["ryzen 5 5600", "ryzen 7 5700x"], "negative_search_terms": ["faulty"]},
            "gpu": {"candidate_models": ["RTX 3060 Ti", "RTX 3070", "RX 6700 XT"], "target_price": 120, "walk_away_price": 170,
                    "search_terms": ["rtx 3060 ti white", "rtx 3070 white", "white gpu"], "negative_search_terms": ["mining", "faulty"]},
            "ram": {"candidate_models": ["16GB DDR4 RGB", "32GB DDR4 RGB", "Corsair Vengeance RGB", "G.Skill Trident Z RGB"],
                    "target_price": 35, "walk_away_price": 65,
                    "search_terms": ["rgb ram ddr4", "corsair vengeance rgb", "gskill trident rgb"], "negative_search_terms": []},
            "case": {"candidate_models": ["Lian Li PC-O11", "NZXT H510 Elite", "Corsair 4000D Airflow White", "Phanteks P400A White"],
                     "target_price": 40, "walk_away_price": 80,
                     "search_terms": ["white gaming case", "rgb gaming case", "panoramic case", "fish tank case"], "negative_search_terms": ["damaged", "cracked"]},
            "storage": {"candidate_models": ["1TB NVMe SSD"], "target_price": 35, "walk_away_price": 55,
                        "search_terms": ["1tb nvme ssd"], "negative_search_terms": []},
            "psu": {"candidate_models": ["650W White PSU", "Corsair RM650 White"], "target_price": 45, "walk_away_price": 75,
                    "search_terms": ["white modular psu", "650w white power supply"], "negative_search_terms": ["faulty"]},
            "rgb_fans": {"candidate_models": ["Lian Li UNI FAN SL120", "ARGB 120mm fans", "Corsair LL120"],
                         "target_price": 30, "walk_away_price": 60,
                         "search_terms": ["argb 120mm fans", "lian li fans", "rgb case fans"], "negative_search_terms": []},
        },
        "seasonality": {"jan": 4, "feb": 4, "mar": 5, "apr": 6, "may": 6, "jun": 6, "jul": 7, "aug": 7,
                        "sep": 7, "oct": 8, "nov": 10, "dec": 9,
                        "peak_months": ["november", "december"], "slow_months": ["january", "february"],
                        "current_position": "mid_season", "days_until_peak": 145},
    },
    {
        "name": "Competitive Gaming Build",
        "emoji": "⚡",
        "status": "active",
        "target_use_case": "gaming",
        "target_customer": "FPS Crowd",
        "what_they_use_it_for": "CS2, Valorant, Apex Legends, Rainbow Six, maximum FPS at 1080p",
        "what_they_want_from_build": "Maximum FPS, low latency, fast RAM, strong gaming CPU, strong GPU",
        "critical_success_factors": ["High clock speed CPU", "Fast DDR4/DDR5 RAM", "240Hz+ capable GPU", "Low latency"],
        "profit_opportunity_score": 4.0,
        "market_size_score": 7.0,
        "resellability_score": 7.0,
        "liquidity_score": 7.0,
        "risk_score": 3.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 16, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["gaming pc 144hz", "competitive gaming pc", "esports pc build", "cs2 gaming pc"],
            "price_min": 120, "price_max": 350, "listing_types": ["buy_it_now", "auction"]
        },
        "profit_strategy": {"target_profit_gbp": 120, "target_margin_pct": 38, "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell"},
        "ideal_build": {
            "cpu": {"candidate_models": ["Ryzen 5 5600X", "Ryzen 7 5800X3D", "i5-12600K", "i5-13600K"],
                    "target_price": 75, "walk_away_price": 120,
                    "search_terms": ["ryzen 5 5600x", "ryzen 7 5800x3d", "i5 12600k"], "negative_search_terms": ["faulty"]},
            "gpu": {"candidate_models": ["RTX 3060 Ti", "RTX 3070", "RX 6700 XT"],
                    "target_price": 110, "walk_away_price": 165,
                    "search_terms": ["rtx 3060 ti", "rtx 3070", "rx 6700 xt"], "negative_search_terms": ["mining", "faulty"]},
            "ram": {"candidate_models": ["16GB DDR4 3600MHz CL16", "32GB DDR4 3600MHz"],
                    "target_price": 30, "walk_away_price": 55,
                    "search_terms": ["ddr4 3600mhz", "fast gaming ram", "cl16 ddr4"], "negative_search_terms": []},
            "storage": {"candidate_models": ["500GB NVMe Gen4", "1TB NVMe Gen4"],
                        "target_price": 30, "walk_away_price": 55,
                        "search_terms": ["gen4 nvme", "fast nvme ssd"], "negative_search_terms": []},
            "psu": {"candidate_models": ["650W 80+ Gold"],
                    "target_price": 35, "walk_away_price": 60,
                    "search_terms": ["650w gold psu"], "negative_search_terms": ["faulty"]},
        },
        "seasonality": {"jan": 5, "feb": 5, "mar": 6, "apr": 6, "may": 7, "jun": 8, "jul": 8, "aug": 7,
                        "sep": 7, "oct": 8, "nov": 9, "dec": 8,
                        "peak_months": ["june", "july", "november"], "slow_months": ["january", "february"],
                        "current_position": "in_season", "days_until_peak": 60},
    },
    {
        "name": "Student Build",
        "emoji": "🎓",
        "status": "active",
        "target_use_case": "budget",
        "target_customer": "University Students",
        "what_they_use_it_for": "Assignments, light gaming, streaming, Discord, Zoom calls, coding basics",
        "what_they_want_from_build": "Reliable, fast enough for multitasking, SSD for boot speed, budget",
        "critical_success_factors": ["Fast SSD", "8-16GB RAM", "Reliable CPU", "Price under £250", "Good for productivity"],
        "profit_opportunity_score": 4.0,
        "market_size_score": 8.0,
        "resellability_score": 7.0,
        "liquidity_score": 8.0,
        "risk_score": 3.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i5", "ram_min_gb": 8, "gpu_required": False, "psu_required": True},
        "search_strategy": {
            "keywords": ["student pc", "office pc no gpu", "HP EliteDesk", "Dell OptiPlex", "ex office pc"],
            "price_min": 30, "price_max": 130, "listing_types": ["buy_it_now", "auction"]
        },
        "profit_strategy": {"target_profit_gbp": 70, "target_margin_pct": 45, "sell_platform": "eBay", "flip_structure": "buy_clean_sell",
                             "notes": "Clean up, add SSD if missing, price at £150-200 for quick sale."},
        "ideal_build": {
            "cpu": {"candidate_models": ["i5-8500", "i5-9400", "i5-10400", "Ryzen 5 3600"],
                    "target_price": 20, "walk_away_price": 40,
                    "search_terms": ["i5 office pc", "dell optiplex i5", "hp elitedesk i5"], "negative_search_terms": ["faulty", "no power"]},
            "ram": {"candidate_models": ["8GB DDR4", "16GB DDR4"],
                    "target_price": 10, "walk_away_price": 20,
                    "search_terms": ["8gb ddr4 ram", "16gb ddr4"], "negative_search_terms": []},
            "storage": {"candidate_models": ["256GB SSD", "500GB SSD"],
                        "target_price": 15, "walk_away_price": 30,
                        "search_terms": ["256gb ssd", "500gb ssd sata"], "negative_search_terms": []},
            "psu": {"candidate_models": ["SFF PSU 260W", "Slim PSU 300W"],
                    "target_price": 10, "walk_away_price": 20,
                    "search_terms": ["sff psu", "small form factor power supply"], "negative_search_terms": ["faulty"]},
        },
        "seasonality": {"jan": 3, "feb": 4, "mar": 5, "apr": 5, "may": 6, "jun": 6, "jul": 7, "aug": 10,
                        "sep": 9, "oct": 7, "nov": 6, "dec": 5,
                        "peak_months": ["august", "september"], "slow_months": ["january", "february"],
                        "current_position": "approaching_peak", "days_until_peak": 75},
    },
    {
        "name": "Developer Workstation",
        "emoji": "💻",
        "status": "active",
        "target_use_case": "workstation",
        "target_customer": "Developers",
        "what_they_use_it_for": "Docker, virtual machines, databases, local services, VS Code, coding agents, Node.js, Python",
        "what_they_want_from_build": "Core count, RAM capacity (32GB+), NVMe speed and capacity, reliability, ECC if possible",
        "critical_success_factors": ["8+ core CPU", "32GB+ RAM", "Fast NVMe 1TB+", "Reliable brand", "Good thermals"],
        "profit_opportunity_score": 3.0,
        "market_size_score": 6.0,
        "resellability_score": 6.0,
        "liquidity_score": 5.0,
        "risk_score": 4.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "i7", "ram_min_gb": 32, "gpu_required": False, "psu_required": True},
        "search_strategy": {
            "keywords": ["hp workstation", "dell precision", "workstation pc", "hp z440", "hp z640", "threadripper workstation"],
            "price_min": 80, "price_max": 300, "listing_types": ["buy_it_now", "auction"]
        },
        "profit_strategy": {"target_profit_gbp": 110, "target_margin_pct": 35, "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell"},
        "ideal_build": {
            "cpu": {"candidate_models": ["Ryzen 7 5700X", "Ryzen 9 5900X", "i7-10700K", "Xeon E5-2690 v4"],
                    "target_price": 80, "walk_away_price": 130,
                    "search_terms": ["ryzen 9 5900x", "i7 10700k", "xeon e5"], "negative_search_terms": ["faulty", "damaged"]},
            "ram": {"candidate_models": ["32GB DDR4 ECC", "64GB DDR4", "32GB DDR4 3200MHz"],
                    "target_price": 40, "walk_away_price": 80,
                    "search_terms": ["32gb ddr4 ecc", "64gb ddr4 workstation"], "negative_search_terms": []},
            "storage": {"candidate_models": ["1TB NVMe SSD", "2TB NVMe SSD"],
                        "target_price": 40, "walk_away_price": 70,
                        "search_terms": ["1tb nvme", "2tb nvme ssd"], "negative_search_terms": []},
            "psu": {"candidate_models": ["750W 80+ Gold", "850W 80+ Gold"],
                    "target_price": 40, "walk_away_price": 70,
                    "search_terms": ["750w gold psu", "850w psu"], "negative_search_terms": ["faulty"]},
        },
        "seasonality": {"jan": 7, "feb": 7, "mar": 8, "apr": 8, "may": 8, "jun": 8, "jul": 7, "aug": 7,
                        "sep": 8, "oct": 8, "nov": 7, "dec": 6,
                        "peak_months": ["march", "april", "september"], "slow_months": ["december"],
                        "current_position": "in_season", "days_until_peak": 0},
    },
    {
        "name": "AI Workstation",
        "emoji": "🤖",
        "status": "active",
        "target_use_case": "ai_workstation",
        "target_customer": "LLM / AI Users",
        "what_they_use_it_for": "Ollama, Open WebUI, local LLMs, Stable Diffusion, AI agent workloads, llama.cpp",
        "what_they_want_from_build": "VRAM (24GB+), system RAM (32-64GB), CPU threads, upgradeability",
        "critical_success_factors": ["GPU VRAM 12GB+", "32GB+ system RAM", "Multiple PCIe lanes", "Good cooling", "Upgradeability"],
        "profit_opportunity_score": 3.0,
        "market_size_score": 7.0,
        "resellability_score": 7.0,
        "liquidity_score": 5.0,
        "risk_score": 4.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "i7", "ram_min_gb": 32, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["ai workstation", "rtx 3090 pc", "rtx 4090 pc", "local llm pc", "ml workstation", "ai pc"],
            "price_min": 200, "price_max": 800, "listing_types": ["buy_it_now", "auction"]
        },
        "profit_strategy": {"target_profit_gbp": 150, "target_margin_pct": 30, "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
                             "notes": "AI market growing fast. Buyers pay premium for VRAM. Target developers and AI hobbyists."},
        "ideal_build": {
            "cpu": {"candidate_models": ["Ryzen 9 5900X", "Ryzen 9 7900X", "i9-12900K"],
                    "target_price": 100, "walk_away_price": 160,
                    "search_terms": ["ryzen 9 5900x", "i9 12900k"], "negative_search_terms": ["faulty"]},
            "gpu": {"candidate_models": ["RTX 3090", "RTX 4090", "RTX 3090 Ti", "RTX 4080"],
                    "target_price": 300, "walk_away_price": 500,
                    "search_terms": ["rtx 3090", "rtx 4090", "24gb vram gpu"], "negative_search_terms": ["faulty", "mining", "blower"]},
            "ram": {"candidate_models": ["64GB DDR4", "128GB DDR4 ECC"],
                    "target_price": 60, "walk_away_price": 110,
                    "search_terms": ["64gb ddr4", "128gb ddr4 ecc server ram"], "negative_search_terms": []},
            "storage": {"candidate_models": ["2TB NVMe SSD", "4TB NVMe SSD"],
                        "target_price": 70, "walk_away_price": 120,
                        "search_terms": ["2tb nvme", "4tb nvme ssd"], "negative_search_terms": []},
            "psu": {"candidate_models": ["1000W 80+ Gold", "1200W 80+ Platinum"],
                    "target_price": 60, "walk_away_price": 100,
                    "search_terms": ["1000w psu", "1200w platinum psu"], "negative_search_terms": ["faulty"]},
        },
        "seasonality": {"jan": 7, "feb": 8, "mar": 8, "apr": 9, "may": 9, "jun": 9, "jul": 8, "aug": 8,
                        "sep": 8, "oct": 8, "nov": 8, "dec": 7,
                        "peak_months": ["april", "may", "june"], "slow_months": ["december"],
                        "current_position": "in_peak", "days_until_peak": 0},
    },
    {
        "name": "Content Creator",
        "emoji": "🎬",
        "status": "active",
        "target_use_case": "workstation",
        "target_customer": "Streamers / Editors",
        "what_they_use_it_for": "Adobe Premiere, DaVinci Resolve, OBS streaming, After Effects, Photoshop, YouTube",
        "what_they_want_from_build": "Fast CPU for rendering, dedicated GPU for encoding, 32GB+ RAM, fast storage",
        "critical_success_factors": ["Fast multi-core CPU", "32GB RAM", "GPU with NVENC/HEVC", "Fast 2TB+ storage", "Reliable"],
        "profit_opportunity_score": 3.0,
        "market_size_score": 6.0,
        "resellability_score": 6.0,
        "liquidity_score": 5.0,
        "risk_score": 4.0,
        "market_growth_direction": "Growing",
        "requirements": {"cpu_min_tier": "i7", "ram_min_gb": 32, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["content creator pc", "video editing pc", "streaming pc", "ryzen 9 desktop", "i9 desktop"],
            "price_min": 120, "price_max": 400, "listing_types": ["buy_it_now", "auction"]
        },
        "profit_strategy": {"target_profit_gbp": 130, "target_margin_pct": 35, "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell"},
        "ideal_build": {
            "cpu": {"candidate_models": ["Ryzen 9 5900X", "Ryzen 9 5950X", "i9-10900K", "i9-12900K"],
                    "target_price": 100, "walk_away_price": 160,
                    "search_terms": ["ryzen 9 5900x", "i9 10900k", "i9 12900k"], "negative_search_terms": ["faulty"]},
            "gpu": {"candidate_models": ["RTX 3070 Ti", "RTX 3080", "RTX 4070"],
                    "target_price": 170, "walk_away_price": 260,
                    "search_terms": ["rtx 3080", "rtx 4070", "rtx 3070 ti"], "negative_search_terms": ["mining", "faulty"]},
            "ram": {"candidate_models": ["32GB DDR4", "64GB DDR4"],
                    "target_price": 40, "walk_away_price": 75,
                    "search_terms": ["32gb ddr4", "64gb ddr4"], "negative_search_terms": []},
            "storage": {"candidate_models": ["2TB NVMe SSD", "2TB Samsung 970 Evo"],
                        "target_price": 55, "walk_away_price": 90,
                        "search_terms": ["2tb nvme ssd", "samsung 970 evo 2tb"], "negative_search_terms": []},
            "psu": {"candidate_models": ["850W 80+ Gold", "1000W 80+ Gold"],
                    "target_price": 50, "walk_away_price": 85,
                    "search_terms": ["850w gold psu", "1000w psu"], "negative_search_terms": ["faulty"]},
        },
        "seasonality": {"jan": 5, "feb": 5, "mar": 6, "apr": 7, "may": 7, "jun": 7, "jul": 7, "aug": 7,
                        "sep": 7, "oct": 8, "nov": 9, "dec": 8,
                        "peak_months": ["october", "november"], "slow_months": ["january", "february"],
                        "current_position": "mid_season", "days_until_peak": 120},
    },
    {
        "name": "Ultra Budget Flip",
        "emoji": "💰",
        "status": "active",
        "target_use_case": "budget",
        "target_customer": "Facebook Marketplace Buyers",
        "what_they_use_it_for": "Basic web browsing, word processing, email, light media, kids' first PC",
        "what_they_want_from_build": "Just works, cheap price, SSD is a bonus, anything under £150",
        "critical_success_factors": ["Price under £150", "Working condition", "Fast boot SSD", "Clean install Windows"],
        "profit_opportunity_score": 4.0,
        "market_size_score": 9.0,
        "resellability_score": 8.0,
        "liquidity_score": 10.0,
        "risk_score": 2.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i3", "ram_min_gb": 4, "gpu_required": False, "psu_required": True},
        "search_strategy": {
            "keywords": ["job lot pcs", "bulk office pcs", "ex lease pc", "computer bundle", "joblot computers", "pc lot clearance"],
            "price_min": 5, "price_max": 60, "listing_types": ["buy_it_now", "auction"]
        },
        "profit_strategy": {"target_profit_gbp": 50, "target_margin_pct": 55, "sell_platform": "eBay", "flip_structure": "buy_clean_sell",
                             "notes": "Buy lots of 5-10, clean and sell individually. High volume, low margin per unit."},
        "ideal_build": {
            "cpu": {"candidate_models": ["i3-8100", "i5-7500", "i5-8400", "i3-10100"],
                    "target_price": 8, "walk_away_price": 20,
                    "search_terms": ["job lot pcs", "bulk pcs office", "i5 desktop lot"], "negative_search_terms": ["no hdd only", "scrap", "water damaged"]},
            "ram": {"candidate_models": ["4GB DDR4", "8GB DDR4"],
                    "target_price": 5, "walk_away_price": 12,
                    "search_terms": ["4gb ddr4 lot", "8gb ddr4 used"], "negative_search_terms": []},
            "storage": {"candidate_models": ["120GB SSD", "240GB SSD"],
                        "target_price": 8, "walk_away_price": 18,
                        "search_terms": ["120gb ssd lot", "240gb ssd"], "negative_search_terms": []},
        },
        "seasonality": {"jan": 6, "feb": 6, "mar": 7, "apr": 7, "may": 7, "jun": 7, "jul": 7, "aug": 8,
                        "sep": 8, "oct": 8, "nov": 9, "dec": 9,
                        "peak_months": ["november", "december", "august"], "slow_months": [],
                        "current_position": "in_season", "days_until_peak": 0},
    },
    {
        "name": "Premium Showcase",
        "emoji": "👑",
        "status": "active",
        "target_use_case": "gaming",
        "target_customer": "High-end Buyers",
        "what_they_use_it_for": "4K gaming, VR, content creation, prestige ownership, top-tier performance",
        "what_they_want_from_build": "Best-in-class specs, premium case, 4K capable GPU, looks impressive",
        "critical_success_factors": ["RTX 4080/4090 GPU", "Latest gen CPU", "DDR5 RAM", "Premium case", "Premium brand parts"],
        "profit_opportunity_score": 2.0,
        "market_size_score": 4.0,
        "resellability_score": 5.0,
        "liquidity_score": 3.0,
        "risk_score": 7.0,
        "market_growth_direction": "Stable",
        "requirements": {"cpu_min_tier": "i9", "ram_min_gb": 32, "gpu_required": True, "psu_required": True},
        "search_strategy": {
            "keywords": ["rtx 4090 pc", "rtx 4080 gaming pc", "high end gaming pc", "threadripper build"],
            "price_min": 500, "price_max": 2000, "listing_types": ["buy_it_now"]
        },
        "profit_strategy": {"target_profit_gbp": 200, "target_margin_pct": 25, "sell_platform": "eBay", "flip_structure": "buy_upgrade_sell",
                             "notes": "High value, slower sales. Needs premium listing photos and detailed spec sheet."},
        "ideal_build": {
            "cpu": {"candidate_models": ["i9-13900K", "i9-14900K", "Ryzen 9 7950X", "Ryzen 9 7900X3D"],
                    "target_price": 200, "walk_away_price": 320,
                    "search_terms": ["i9 13900k", "ryzen 9 7950x"], "negative_search_terms": ["faulty"]},
            "gpu": {"candidate_models": ["RTX 4090", "RTX 4080", "RTX 4080 Super"],
                    "target_price": 600, "walk_away_price": 900,
                    "search_terms": ["rtx 4090", "rtx 4080"], "negative_search_terms": ["faulty", "mining"]},
            "ram": {"candidate_models": ["32GB DDR5 6000MHz", "64GB DDR5"],
                    "target_price": 80, "walk_away_price": 140,
                    "search_terms": ["ddr5 32gb", "ddr5 6000mhz ram"], "negative_search_terms": []},
            "storage": {"candidate_models": ["2TB NVMe Gen5", "4TB NVMe SSD"],
                        "target_price": 100, "walk_away_price": 170,
                        "search_terms": ["gen5 nvme 2tb", "4tb nvme ssd"], "negative_search_terms": []},
            "case": {"candidate_models": ["Lian Li O11 XL", "Phanteks Enthoo 719", "Corsair 7000D"],
                     "target_price": 80, "walk_away_price": 150,
                     "search_terms": ["premium gaming case", "full tower case", "lian li o11"], "negative_search_terms": ["damaged", "cracked"]},
            "psu": {"candidate_models": ["1200W 80+ Platinum", "1000W 80+ Titanium"],
                    "target_price": 100, "walk_away_price": 170,
                    "search_terms": ["1200w platinum psu", "1000w titanium psu"], "negative_search_terms": ["faulty"]},
        },
        "seasonality": {"jan": 4, "feb": 4, "mar": 4, "apr": 5, "may": 5, "jun": 5, "jul": 5, "aug": 5,
                        "sep": 5, "oct": 6, "nov": 9, "dec": 10,
                        "peak_months": ["november", "december"], "slow_months": ["january", "february", "march"],
                        "current_position": "slow_season", "days_until_peak": 160},
    },
]


async def seed_playbooks(db: AsyncSession) -> int:
    """Insert any of the 10 canonical playbooks that don't already exist. Returns count created."""
    created = 0
    for data in _INITIAL_PLAYBOOKS:
        result = await db.execute(
            select(Playbook).where(Playbook.name == data["name"])
        )
        if result.scalar_one_or_none() is not None:
            continue
        pb = Playbook(
            **data,
            activated_at=datetime.utcnow(),
        )
        db.add(pb)
        created += 1
    await db.commit()
    return created
```

- [ ] **Step 2: Trigger seed via API**

```bash
curl -s -X POST http://andromeda-ts:4311/api/playbooks/seed | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))"
```
Expected: `{"ok": true, "created": 10}`

- [ ] **Step 3: Verify**

```bash
curl -s http://andromeda-ts:4311/api/playbooks | python3 -c "import json,sys; pbs=json.load(sys.stdin); print(f'{len(pbs)} playbooks'); [print(f'  {p[\"emoji\"]} {p[\"name\"]} ({p[\"status\"]})') for p in pbs]"
```
Expected: 10 playbooks listed.

- [ ] **Step 4: Commit and push**

```bash
git add pc-flipper-backend/app/services/playbook_seeder.py pc-flipper-backend/app/api/playbooks.py
git commit -m "feat: seed 10 canonical playbooks with full customer profiles and ideal builds"
git push origin master
```

---

### Task 4: Rewrite Evolution Engine (9 Phases)

**Files:**
- Modify: `pc-flipper-backend/app/services/playbook_evolution.py` (rewrite the `run_playbook_evolution` function and add phase helpers)

- [ ] **Step 1: Replace `run_playbook_evolution` with full 9-phase engine**

Replace the `run_playbook_evolution` function and add phase helpers. The core logic in `playbook_evolution.py` below `run_playbook_evolution`:

```python
# ─── Phase helpers ────────────────────────────────────────────────────────────

def _compute_market_size_score(listing_count: int, gem_count: int) -> float:
    """0-10 score: more active listings + gems = larger addressable market."""
    base = min(10.0, listing_count / 20.0)
    gem_boost = min(2.0, gem_count / 5.0)
    return round(min(10.0, base + gem_boost), 1)


def _compute_liquidity_score(avg_days_to_sell: float | None) -> float:
    """0-10 score: faster sales = higher liquidity. <7 days = 9+, >60 days = 1."""
    if avg_days_to_sell is None:
        return 5.0
    if avg_days_to_sell <= 3:
        return 10.0
    if avg_days_to_sell <= 7:
        return 9.0
    if avg_days_to_sell <= 14:
        return 7.5
    if avg_days_to_sell <= 30:
        return 5.5
    if avg_days_to_sell <= 60:
        return 3.0
    return 1.0


def _compute_resellability_score(sold_count: int, listing_count: int, gem_count: int) -> float:
    """0-10: sell-through rate proxy."""
    if listing_count == 0:
        return 5.0
    sell_through = min(1.0, sold_count / max(1, listing_count))
    base = sell_through * 8.0
    gem_boost = min(2.0, gem_count / 3.0)
    return round(min(10.0, base + gem_boost), 1)


def _compute_risk_score(avg_days_to_sell: float | None, margin_pct: float | None, listing_count: int) -> float:
    """0-10: higher = more risky. Slow sales + low margin + thin market = high risk."""
    risk = 3.0
    if avg_days_to_sell and avg_days_to_sell > 30:
        risk += 2.0
    if avg_days_to_sell and avg_days_to_sell > 60:
        risk += 1.5
    if margin_pct and margin_pct < 20:
        risk += 2.0
    if listing_count < 5:
        risk += 1.0
    return round(min(10.0, risk), 1)


def _compute_composite_rank(
    profit_opportunity_score: float,
    market_size_score: float,
    liquidity_score: float,
    resellability_score: float,
    risk_score: float,
    expected_roi_pct: float,
) -> float:
    """
    Composite rank = ROI × Demand × Liquidity × Resellability × Profit Opportunity × (1 / Risk)
    Normalised to 0-100.
    """
    roi_factor = min(3.0, max(0.1, expected_roi_pct / 40.0))
    demand_factor = market_size_score / 10.0
    liquidity_factor = liquidity_score / 10.0
    resellability_factor = resellability_score / 10.0
    profit_factor = profit_opportunity_score / 5.0
    risk_factor = max(0.1, (10.0 - risk_score) / 10.0)
    raw = roi_factor * demand_factor * liquidity_factor * resellability_factor * profit_factor * risk_factor
    return round(min(100.0, raw * 100.0), 2)


async def _refresh_playbook_scores(db, playbook: "Playbook", sold_flips: list, demand_categories: list) -> None:
    """
    Phases 2-9: update all scores on a single playbook in-place.
    Uses sold flip history + demand signals for scoring.
    """
    from datetime import timedelta

    # Phase 3: Component pricing — use existing profit_strategy target as baseline
    # (Full eBay pricing refresh per component is done in the daily scrape cycle)

    # Phase 4/5: Build cost + Profit range from sold flips matching this playbook
    use_case = str(playbook.target_use_case or "").lower()
    matching_flips = [
        f for f in sold_flips
        if f.actual_profit is not None
    ]

    if matching_flips:
        profits = [float(f.actual_profit) for f in matching_flips]
        min_profit = round(min(profits), 0)
        max_profit = round(max(profits), 0)
        expected_profit = round(sum(profits) / len(profits), 0)
    else:
        ps = dict(playbook.profit_strategy or {})
        expected_profit = float(ps.get("target_profit_gbp") or 0)
        min_profit = round(expected_profit * 0.6, 0)
        max_profit = round(expected_profit * 1.5, 0)

    pricing_model = dict(playbook.pricing_model or {})
    expected_build = float(pricing_model.get("expected_build_cost") or 0)

    expected_roi_pct = 0.0
    if expected_build > 0 and expected_profit > 0:
        sell_price = expected_build + expected_profit
        expected_roi_pct = round((expected_profit / expected_build) * 100, 1)

    playbook.profit_model = {
        "minimum_profit": min_profit,
        "expected_profit": expected_profit,
        "maximum_profit": max_profit,
        "expected_roi_pct": expected_roi_pct,
    }

    # Phase 6: Market size — from demand_categories matching use_case
    _USE_CASE_CAT_MAP = {
        "gaming": ["Gaming PCs", "Budget Builders"],
        "budget": ["Budget Builders", "Office Clearance"],
        "workstation": ["Workstations"],
        "office": ["Office Clearance"],
        "ai_workstation": ["Workstations"],
        "htpc": ["HTPC / SFF"],
    }
    relevant_cats = _USE_CASE_CAT_MAP.get(use_case, [])
    cat_listings = sum(c.get("count", 0) for c in demand_categories if c.get("name") in relevant_cats)
    cat_gems = sum(c.get("gem_count", 0) for c in demand_categories if c.get("name") in relevant_cats)
    playbook.market_size_score = _compute_market_size_score(cat_listings, cat_gems)

    # Phase 7: Liquidity
    avg_days = float(playbook.avg_days_to_sell or 14)
    playbook.liquidity_score = _compute_liquidity_score(avg_days)

    # Phase 8: Resellability
    sold_count = len(matching_flips)
    playbook.resellability_score = _compute_resellability_score(sold_count, max(1, cat_listings), cat_gems)

    # Phase 9: Risk
    margin_pct = expected_roi_pct if expected_roi_pct > 0 else None
    playbook.risk_score = _compute_risk_score(avg_days, margin_pct, cat_listings)

    # Growth direction from demand categories
    trend_votes = [c.get("trend", "") for c in demand_categories if c.get("name") in relevant_cats]
    growing = sum(1 for t in trend_votes if t == "Growing")
    shrinking = sum(1 for t in trend_votes if t == "Shrinking")
    if growing > shrinking:
        playbook.market_growth_direction = "Growing"
    elif shrinking > growing:
        playbook.market_growth_direction = "Shrinking"
    else:
        playbook.market_growth_direction = "Stable"

    # Composite rank
    playbook.composite_rank_score = _compute_composite_rank(
        playbook.profit_opportunity_score,
        playbook.market_size_score,
        playbook.liquidity_score,
        playbook.resellability_score,
        playbook.risk_score,
        expected_roi_pct,
    )

    playbook.last_reviewed = datetime.utcnow()
```

Then replace the `run_playbook_evolution` function signature to also call `_refresh_playbook_scores` for every active playbook:

```python
async def run_playbook_evolution() -> dict:
    """
    Daily evolution engine — 9 phases.
    Returns summary dict with proposals_created, playbooks_scored, search_terms changes.
    """
    cutoff = datetime.utcnow() - timedelta(days=30)

    async with AsyncSessionLocal() as db:
        flips_result = await db.execute(
            select(Flip).where(
                and_(
                    Flip.stage == FlipStage.sold,
                    Flip.sold_at.is_not(None),
                    Flip.sold_at >= cutoff,
                    Flip.actual_profit.is_not(None),
                )
            )
        )
        sold_flips = list(flips_result.scalars().all())

        playbooks_result = await db.execute(select(Playbook).where(Playbook.status == "active"))
        playbooks = list(playbooks_result.scalars().all())

        demand_categories = await compute_demand(db)
        external = await latest_external_signal_snapshot(limit_per_source=50)

        # Phase 2: Validate / score all active playbooks
        playbooks_scored = 0
        for pb in playbooks:
            await _refresh_playbook_scores(db, pb, sold_flips, demand_categories)
            playbooks_scored += 1

        await db.flush()

        # Existing proposal logic (profit target adjustments + demand-driven CREATE proposals)
        proposals_created = 0
        gt = _latest_query_signal_map(external)
        score_ai = _score_for(gt, "ai pc")
        score_gaming = _score_for(gt, "gaming pc")
        score_budget = _score_for(gt, "budget gaming pc")
        score_workstation = _score_for(gt, "workstation pc")

        async def _apply_rule_to_use_case(use_case, *, trigger_score, threshold, marker, reason, keyword_add, target_profit_multiplier=None):
            if trigger_score < threshold:
                return 0
            created = 0
            for pb in playbooks:
                if str(pb.target_use_case or "").lower() != use_case:
                    continue
                ok = await _create_demand_rule_update(db, pb, reason=reason, marker=marker,
                    demand_signals={"source": marker, "query_score": round(trigger_score, 2),
                                    "threshold": threshold, "external_summary": external.get("summary", {})},
                    keyword_add=keyword_add, target_profit_multiplier=target_profit_multiplier)
                if ok:
                    created += 1
            return created

        proposals_created += await _apply_rule_to_use_case("ai_workstation", trigger_score=score_ai, threshold=5.0,
            marker="demand_rules_v1_ai_pc", reason="Google Trends shows elevated 'ai pc' demand.",
            keyword_add=["ai pc", "ai workstation", "local llm pc"], target_profit_multiplier=1.08)
        proposals_created += await _apply_rule_to_use_case("gaming", trigger_score=score_gaming, threshold=4.0,
            marker="demand_rules_v1_gaming_pc", reason="Gaming PC demand rising.",
            keyword_add=["gaming pc", "custom gaming pc"], target_profit_multiplier=1.05)
        proposals_created += await _apply_rule_to_use_case("budget", trigger_score=score_budget, threshold=2.0,
            marker="demand_rules_v1_budget_gaming_pc", reason="Budget gaming demand rising.",
            keyword_add=["budget gaming pc", "cheap gaming pc"], target_profit_multiplier=1.04)
        proposals_created += await _apply_rule_to_use_case("workstation", trigger_score=score_workstation, threshold=2.0,
            marker="demand_rules_v1_workstation_pc", reason="Workstation demand rising.",
            keyword_add=["workstation pc", "cad workstation"], target_profit_multiplier=1.04)

        # Profit target proposals from sold flip outcomes
        if sold_flips and playbooks:
            avg_profit = sum(float(f.actual_profit or 0) for f in sold_flips) / max(1, len(sold_flips))
            for pb in playbooks:
                strategy = dict(pb.profit_strategy or {})
                target_profit = float(strategy.get("target_profit_gbp") or 0)
                if target_profit <= 0:
                    continue
                delta = avg_profit - target_profit
                if abs(delta) / max(1.0, target_profit) < 0.12:
                    continue
                existing = await db.execute(select(PlaybookProposal).where(
                    and_(PlaybookProposal.playbook_id == pb.id,
                         PlaybookProposal.action == "UPDATE",
                         PlaybookProposal.status == "pending")))
                if existing.scalar_one_or_none() is not None:
                    continue
                variant = "A" if (pb.id % 2 == 0) else "B"
                multiplier = (1.10 if variant == "A" else 1.07) if delta > 0 else (0.90 if variant == "A" else 0.93)
                new_strategy = dict(strategy)
                new_strategy["target_profit_gbp"] = max(20.0, round(target_profit * multiplier, 0))
                reason = "Sold outcomes outperforming target." if delta > 0 else "Sold outcomes underperforming target."
                db.add(PlaybookProposal(action="UPDATE", playbook_id=pb.id,
                    proposed_data={"profit_strategy": new_strategy}, reason=reason,
                    demand_signals={"source": "playbook_evolution_v1", "avg_actual_profit": round(avg_profit, 2),
                                    "old_target_profit": target_profit, "ab_variant": variant},
                    status="pending", proposed_at=datetime.utcnow()))
                proposals_created += 1

        await db.commit()

    terms_result = await _sync_search_terms(external, demand_categories)
    log.info("playbook_evolution.done", proposals_created=proposals_created,
             playbooks_scored=playbooks_scored, terms_upserted=terms_result.get("upserted", 0))
    return {
        "ok": True,
        "proposals_created": proposals_created,
        "playbooks_scored": playbooks_scored,
        "sold_flips": len(sold_flips),
        "terms_upserted": terms_result.get("upserted", 0),
    }
```

- [ ] **Step 2: Trigger evolution run to verify scoring works**

```bash
docker exec flipflop-backend python3 -c "
import asyncio
from app.services.playbook_evolution import run_playbook_evolution
result = asyncio.run(run_playbook_evolution())
import json; print(json.dumps(result, indent=2))
"
```
Expected: `{"ok": true, "playbooks_scored": 10, ...}`

- [ ] **Step 3: Verify scores are stored**

```bash
curl -s http://andromeda-ts:4311/api/playbooks/ranked | python3 -c "
import json,sys
pbs = json.load(sys.stdin)
for p in pbs[:5]:
    print(f'{p[\"name\"]}: rank={p[\"composite_rank_score\"]} market={p[\"market_size_score\"]} liquidity={p[\"liquidity_score\"]}')
"
```

- [ ] **Step 4: Commit and push**

```bash
git add pc-flipper-backend/app/services/playbook_evolution.py
git commit -m "feat: rewrite evolution engine with full 9-phase scoring (market size, liquidity, resellability, risk, composite rank)"
git push origin master
```

---

### Task 5: Search Term Strategy Rewrite

**Files:**
- Modify: `pc-flipper-backend/app/services/playbook_evolution.py` (replace `_BASELINE_TERMS` + `_sync_search_terms`)

- [ ] **Step 1: Replace `_BASELINE_TERMS` with spec-aligned catalog structure**

Replace the `_BASELINE_TERMS` dict in `playbook_evolution.py`:

```python
# ── Static baseline terms per catalogue ───────────────────────────────────────
# flip_opportunities: static terms always present
_FLIP_STATIC_TERMS = [
    {"term": "ex-workstation pc builds",  "group": "static"},
    {"term": "motherboard cpu combo",      "group": "static"},
    {"term": "HP pc",                      "group": "static"},
    {"term": "Lenovo pc",                  "group": "static"},
    {"term": "Dell pc",                    "group": "static"},
    {"term": "office pc",                  "group": "static"},
    {"term": "No GPU pc",                  "group": "static"},
    {"term": "No memory pc",               "group": "static"},
    {"term": "pc tower",                   "group": "static"},
    {"term": "gaming pc",                  "group": "static"},
    {"term": "desktop pc",                 "group": "static"},
]

# accessories: static, never auto-changed
_ACCESSORY_TERMS = [
    {"term": "gaming keyboard",            "group": "accessories"},
    {"term": "gaming mouse",               "group": "accessories"},
    {"term": "gaming headset",             "group": "accessories"},
    {"term": "gaming monitor",             "group": "accessories"},
    {"term": "gaming controller",          "group": "accessories"},
    {"term": "gaming speakers",            "group": "accessories"},
    {"term": "mechanical keyboard",        "group": "accessories"},
    {"term": "rgb keyboard",               "group": "accessories"},
    {"term": "wireless gaming mouse",      "group": "accessories"},
    {"term": "webcam streaming",           "group": "accessories"},
]

_BASELINE_TERMS: dict[str, list[dict]] = {
    "flip_opportunities": _FLIP_STATIC_TERMS,
    "accessories": _ACCESSORY_TERMS,
}
```

- [ ] **Step 2: Add `_build_component_terms_from_playbooks` and `_build_case_terms_from_playbooks` helpers**

Add before `_sync_search_terms`:

```python
async def _build_component_terms_from_playbooks(db) -> list[dict]:
    """
    Build generic component search terms from all active playbook ideal_build fields.
    Returns a list of {term, group} dicts.
    """
    result = await db.execute(select(Playbook).where(Playbook.status == "active"))  # noqa
    playbooks = result.scalars().all()

    terms: set[str] = set()
    # Always-present generic component terms (spec requirement)
    always = [
        "i5 cpu", "i7 cpu", "i9 cpu", "ryzen cpu", "am4 cpu", "am5 cpu",
        "am4 motherboard", "am5 motherboard", "b450 motherboard", "b550 motherboard",
        "b650 motherboard", "x670 motherboard", "ddr4 ram", "ddr5 ram",
        "32gb ram", "rgb ram", "ddr5 rgb", "650w psu", "750w psu",
        "gaming psu", "nvidia gpu", "amd gpu", "rtx gpu", "radeon gpu",
        "cpu cooler", "aio cooler", "rgb cpu cooler", "rgb fans", "argb fans",
        "nvme ssd", "m.2 ssd",
    ]
    for t in always:
        terms.add(t)

    # Extract component search terms from ideal_build in all active playbooks
    for pb in playbooks:
        ideal = pb.ideal_build or {}
        for component_key, comp_data in ideal.items():
            if component_key in ("case", "rgb_fans"):
                continue  # handled by cases catalogue
            if not isinstance(comp_data, dict):
                continue
            for st in comp_data.get("search_terms", []):
                if st and len(st) > 3:
                    terms.add(str(st).strip().lower())

    return [{"term": t, "group": "components"} for t in sorted(terms)]


async def _build_case_terms_from_playbooks(db) -> list[dict]:
    """
    Build case search terms from case preferences in all active playbook ideal_builds.
    """
    result = await db.execute(select(Playbook).where(Playbook.status == "active"))  # noqa
    playbooks = result.scalars().all()

    terms: set[str] = set()
    base_case_terms = [
        "gaming pc case", "atx gaming case", "rgb gaming case", "white gaming case",
        "tempered glass case", "fish tank case", "panoramic case", "argb case",
        "showcase case", "white pc case", "black rgb case", "micro atx case",
    ]
    for t in base_case_terms:
        terms.add(t)

    for pb in playbooks:
        ideal = pb.ideal_build or {}
        case_data = ideal.get("case", {})
        if isinstance(case_data, dict):
            for st in case_data.get("search_terms", []):
                if st and len(st) > 3:
                    terms.add(str(st).strip().lower())

    return [{"term": t, "group": "cases"} for t in sorted(terms)]
```

- [ ] **Step 3: Update `_sync_search_terms` to use the new catalog logic + generate 5 dynamic flip terms**

Replace `_sync_search_terms` with:

```python
async def _sync_search_terms(external: dict, demand_categories: list) -> dict:
    """
    Sync search terms per catalogue spec:
    - flip_opportunities: static terms + 5 dynamic terms from demand data
    - components: generic terms derived from active playbook ideal_builds
    - cases: derived from active playbook case preferences
    - accessories: static
    """
    signal_map = _latest_query_signal_map(external)
    upserted = 0
    disabled = 0

    all_sources = [
        "eBay", "eBay UK", "eBay (Worldwide)", "eBay UK Auctions",
        "Amazon", "Gumtree", "Temu", "AliExpress", "Alibaba",
        "BargainHardware", "CherryTree Inc", "Preloved",
    ]

    async with AsyncSessionLocal() as db:
        # ── 1. Components terms from playbooks ───────────────────────────────
        component_terms = await _build_component_terms_from_playbooks(db)
        case_terms = await _build_case_terms_from_playbooks(db)

        # ── 2. Generate 5 dynamic flip_opportunities terms ───────────────────
        # Pick the top-scoring demand categories and translate to search terms
        sorted_cats = sorted(demand_categories, key=lambda c: c.get("count", 0), reverse=True)
        _CAT_TO_FLIP_TERMS = {
            "Gaming PCs": ["gaming pc", "rtx gaming desktop", "custom gaming build"],
            "Workstations": ["hp workstation", "dell workstation", "ex workstation pc"],
            "Budget Builders": ["budget gaming pc", "no gpu gaming pc", "cheap gaming desktop"],
            "Office Clearance": ["office clearance pc", "ex office desktop pc"],
            "HTPC / SFF": ["mini pc gaming", "small form factor gaming pc"],
        }
        dynamic_terms: list[str] = []
        for cat in sorted_cats:
            if len(dynamic_terms) >= 5:
                break
            candidates = _CAT_TO_FLIP_TERMS.get(cat.get("name", ""), [])
            for t in candidates:
                if t not in dynamic_terms:
                    dynamic_terms.append(t)
                    if len(dynamic_terms) >= 5:
                        break

        # Supplement with Google Trends if we have fewer than 5
        trend_map = {
            "budget gaming pc": "budget gaming pc desktop",
            "ai pc": "AI workstation desktop",
            "white pc build": "white RGB gaming PC",
            "rtx 3070": "RTX 3070 gaming PC build",
            "gaming pc": "gaming pc desktop tower",
        }
        for query, term in trend_map.items():
            if len(dynamic_terms) >= 5:
                break
            if _score_for(signal_map, query) >= 2.0 and term not in dynamic_terms:
                dynamic_terms.append(term)

        # Ensure we always have exactly 5
        fallback = ["AM5 gaming PC", "RTX 4060 gaming desktop", "Ryzen 7 gaming PC",
                    "mini ITX gaming PC", "white RGB gaming PC"]
        for fb in fallback:
            if len(dynamic_terms) >= 5:
                break
            if fb not in dynamic_terms:
                dynamic_terms.append(fb)

        dynamic_term_dicts = [{"term": t, "group": "dynamic"} for t in dynamic_terms[:5]]

        # ── 3. Upsert all terms ───────────────────────────────────────────────
        catalogue_terms: dict[str, list[dict]] = {
            "flip_opportunities": _FLIP_STATIC_TERMS + dynamic_term_dicts,
            "components": component_terms,
            "cases": case_terms,
            "accessories": _ACCESSORY_TERMS,
        }

        for scope, terms in catalogue_terms.items():
            is_static_scope = scope in ("accessories",)
            for entry in terms:
                term_text = entry["term"]
                is_baseline = entry.get("group") in ("static", "accessories", "components", "cases")
                result = await db.execute(
                    select(SourceSearchTerm).where(
                        SourceSearchTerm.scope == scope,
                        SourceSearchTerm.term == term_text,
                    )
                )
                row = result.scalar_one_or_none()
                if row is None:
                    db.add(SourceSearchTerm(
                        scope=scope,
                        group_name=entry.get("group", "baseline"),
                        term=term_text,
                        source_names=all_sources,
                        notes="auto_baseline" if is_baseline else "dynamic",
                        enabled=True,
                        is_baseline=is_baseline,
                        demand_score=5.0,
                    ))
                    upserted += 1
                else:
                    row.enabled = True
                    if is_baseline:
                        row.is_baseline = True
                    if row.demand_score == 0.0:
                        row.demand_score = 5.0

        # ── 4. Auto-disable dead non-baseline terms ───────────────────────────
        dead_result = await db.execute(
            select(SourceSearchTerm).where(
                SourceSearchTerm.is_baseline == False,
                SourceSearchTerm.enabled == True,
                SourceSearchTerm.zero_results_streak >= _ZERO_RESULTS_DISABLE_THRESHOLD,
            )
        )
        for dead in dead_result.scalars().all():
            dead.enabled = False
            disabled += 1

        await db.commit()

    log.info("search_terms.synced", upserted=upserted, disabled=disabled,
             dynamic_flip_terms=dynamic_terms[:5])
    return {"upserted": upserted, "disabled": disabled, "dynamic_flip_terms": dynamic_terms[:5]}
```

- [ ] **Step 4: Rebuild backend and verify terms sync**

```bash
docker compose build backend && docker compose up -d backend
sleep 5
curl -s "http://andromeda-ts:4311/api/source-search-terms?scope=flip_opportunities" | python3 -c "
import json,sys; d=json.load(sys.stdin)
items = d.get('items', d) if isinstance(d, dict) else d
print(f'flip_opportunities terms: {len(items)}')
for i in items[:8]: print(f'  [{i[\"group_name\"]}] {i[\"term\"]}')"
```

- [ ] **Step 5: Commit and push**

```bash
git add pc-flipper-backend/app/services/playbook_evolution.py
git commit -m "feat: rewrite search term strategy with catalog-specific logic and 5 dynamic flip_opportunities terms"
git push origin master
```

---

### Task 6: Frontend — Playbook Dashboard Overhaul

**Files:**
- Modify: `pc-flipper/lib/types.ts` (extend Playbook interface)
- Modify: `pc-flipper/lib/api.ts` (add ranked + seed endpoints)
- Modify: `pc-flipper/app/playbooks/page.tsx` (full dashboard redesign)
- Create: `pc-flipper/components/playbooks/SeasonalityChart.tsx`
- Create: `pc-flipper/components/playbooks/ScoreBadges.tsx`
- Create: `pc-flipper/components/playbooks/IdealBuildPanel.tsx`
- Create: `pc-flipper/components/playbooks/PlaybookDashboard.tsx`

- [ ] **Step 1: Extend Playbook type in `pc-flipper/lib/types.ts`**

Find the `Playbook` interface and replace it:

```typescript
export interface PlaybookSeasonality {
  jan: number; feb: number; mar: number; apr: number;
  may: number; jun: number; jul: number; aug: number;
  sep: number; oct: number; nov: number; dec: number;
  peak_months: string[];
  slow_months: string[];
  current_position: string;
  days_until_peak: number;
}

export interface PlaybookIdealBuildComponent {
  candidate_models: string[];
  target_price: number;
  walk_away_price: number;
  search_terms: string[];
  negative_search_terms: string[];
}

export interface PlaybookPricingModel {
  minimum_build_cost?: number;
  expected_build_cost?: number;
  maximum_build_cost?: number;
}

export interface PlaybookProfitModel {
  minimum_profit?: number;
  expected_profit?: number;
  maximum_profit?: number;
  expected_roi_pct?: number;
}

export interface Playbook {
  id: number;
  name: string;
  description?: string | null;
  emoji?: string;
  status: PlaybookStatus;
  target_use_case: PlaybookUseCase;
  target_customer?: string | null;
  what_they_use_it_for?: string | null;
  what_they_want_from_build?: string | null;
  critical_success_factors: string[];
  requirements: PlaybookRequirements;
  component_catalogue: Record<string, unknown>;
  search_strategy: PlaybookSearchStrategy;
  upgrade_strategy: PlaybookUpgradeStrategy;
  profit_strategy: PlaybookProfitStrategy;
  upsell_strategy: Record<string, unknown>;
  // Scores
  profit_opportunity_score: number;
  market_size_score: number;
  resellability_score: number;
  liquidity_score: number;
  risk_score: number;
  composite_rank_score: number;
  market_growth_direction?: string | null;
  // Intelligence
  seasonality: Partial<PlaybookSeasonality>;
  ideal_build: Record<string, PlaybookIdealBuildComponent>;
  pricing_model: PlaybookPricingModel;
  profit_model: PlaybookProfitModel;
  // Actuals
  flip_count: number;
  avg_profit_gbp: number | null;
  avg_days_to_sell: number | null;
  conversion_rate: number | null;
  last_reviewed: string | null;
  created_at: string;
  updated_at: string;
  activated_at: string | null;
  deprecated_at: string | null;
}
```

- [ ] **Step 2: Add `ranked` and `seed` to API client in `pc-flipper/lib/api.ts`**

Find `api.playbooks` and add:
```typescript
ranked: (): Promise<Playbook[]> =>
  request<Playbook[]>("/playbooks/ranked"),
seed: (): Promise<{ ok: boolean; created: number }> =>
  request<{ ok: boolean; created: number }>("/playbooks/seed", { method: "POST" }),
```

- [ ] **Step 3: Create `pc-flipper/components/playbooks/SeasonalityChart.tsx`**

```tsx
"use client";

import { useMemo } from "react";
import { PlaybookSeasonality } from "@/lib/types";

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const MONTH_KEYS = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"] as const;
const CURRENT_MONTH = new Date().getMonth(); // 0-indexed

export function SeasonalityChart({ seasonality }: { seasonality: Partial<PlaybookSeasonality> }) {
  const values = useMemo(() =>
    MONTH_KEYS.map(k => Number(seasonality[k] ?? 5)),
  [seasonality]);
  const max = Math.max(...values, 1);

  const position = seasonality.current_position ?? "";
  const positionColor =
    position === "in_peak" ? "text-emerald-400" :
    position === "approaching_peak" ? "text-yellow-400" :
    position === "leaving_peak" ? "text-orange-400" :
    position === "slow_season" ? "text-slate-500" : "text-slate-400";

  const positionLabel =
    position === "in_peak" ? "🔥 In Peak Season" :
    position === "approaching_peak" ? "📈 Approaching Peak" :
    position === "leaving_peak" ? "📉 Leaving Peak" :
    position === "slow_season" ? "😴 Slow Season" :
    position === "in_season" ? "✅ In Season" : "—";

  return (
    <div>
      <div className="flex items-end gap-0.5 h-12 mb-1">
        {values.map((v, i) => {
          const isCurrentMonth = i === CURRENT_MONTH;
          const isPeak = (seasonality.peak_months ?? []).includes(MONTHS[i].toLowerCase());
          const height = `${Math.max(8, (v / max) * 100)}%`;
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-0.5">
              <div
                className={`w-full rounded-sm transition-all ${
                  isCurrentMonth
                    ? "bg-[#00dc82]"
                    : isPeak
                    ? "bg-[#00dc82]/50"
                    : "bg-[#1e2d45]"
                }`}
                style={{ height }}
                title={`${MONTHS[i]}: ${v}/10`}
              />
            </div>
          );
        })}
      </div>
      <div className="flex gap-0.5">
        {MONTHS.map((m, i) => (
          <div key={m} className={`flex-1 text-center text-[9px] ${i === CURRENT_MONTH ? "text-[#00dc82] font-bold" : "text-slate-600"}`}>
            {m[0]}
          </div>
        ))}
      </div>
      <div className={`text-xs mt-1.5 font-medium ${positionColor}`}>{positionLabel}</div>
      {(seasonality.days_until_peak ?? 0) > 0 && (
        <div className="text-xs text-slate-500">{seasonality.days_until_peak}d until peak</div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create `pc-flipper/components/playbooks/ScoreBadges.tsx`**

```tsx
"use client";

import { TrendingUp, TrendingDown, Minus, Zap, Users, BarChart2, Clock, AlertTriangle } from "lucide-react";

function ScoreBar({ value, max = 10, color }: { value: number; max?: number; color: string }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="flex-1 h-1 bg-[#1e2d45] rounded-full overflow-hidden">
      <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function ScoreRow({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-slate-500 w-3.5">{icon}</span>
      <span className="text-xs text-slate-500 w-24 shrink-0">{label}</span>
      <ScoreBar value={value} color={color} />
      <span className={`text-xs font-bold w-6 text-right ${color.replace("bg-", "text-").replace("/80","")}`}>
        {value.toFixed(0)}
      </span>
    </div>
  );
}

export function ScoreBadges({ playbook }: { playbook: {
  profit_opportunity_score: number; market_size_score: number;
  resellability_score: number; liquidity_score: number;
  risk_score: number; composite_rank_score: number;
  market_growth_direction?: string | null;
} }) {
  const GrowthIcon = playbook.market_growth_direction === "Growing" ? TrendingUp :
                     playbook.market_growth_direction === "Shrinking" ? TrendingDown : Minus;
  const growthColor = playbook.market_growth_direction === "Growing" ? "text-emerald-400" :
                      playbook.market_growth_direction === "Shrinking" ? "text-red-400" : "text-slate-400";

  return (
    <div className="space-y-1.5">
      <ScoreRow icon={<Zap className="w-3 h-3" />} label="Profit Opp." value={playbook.profit_opportunity_score} color="bg-[#00dc82]/80" />
      <ScoreRow icon={<Users className="w-3 h-3" />} label="Market Size" value={playbook.market_size_score} color="bg-blue-400/80" />
      <ScoreRow icon={<BarChart2 className="w-3 h-3" />} label="Resellability" value={playbook.resellability_score} color="bg-purple-400/80" />
      <ScoreRow icon={<Clock className="w-3 h-3" />} label="Liquidity" value={playbook.liquidity_score} color="bg-yellow-400/80" />
      <ScoreRow icon={<AlertTriangle className="w-3 h-3" />} label="Risk" value={playbook.risk_score} color="bg-red-400/80" />
      <div className="flex items-center gap-2 pt-1 border-t border-[#1e2d45]">
        <GrowthIcon className={`w-3.5 h-3.5 ${growthColor}`} />
        <span className={`text-xs font-medium ${growthColor}`}>{playbook.market_growth_direction ?? "Stable"}</span>
        <span className="ml-auto text-xs font-bold text-[#00dc82]">#{playbook.composite_rank_score.toFixed(0)}</span>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create `pc-flipper/components/playbooks/IdealBuildPanel.tsx`**

```tsx
"use client";

import { PlaybookIdealBuildComponent } from "@/lib/types";

const COMPONENT_LABELS: Record<string, string> = {
  cpu: "CPU", gpu: "GPU", ram: "RAM", storage: "Storage",
  psu: "PSU", case: "Case", motherboard: "Motherboard",
  cooling: "Cooling", rgb_fans: "RGB Fans",
};

export function IdealBuildPanel({ idealBuild }: { idealBuild: Record<string, PlaybookIdealBuildComponent> }) {
  const entries = Object.entries(idealBuild).filter(([, v]) => v && typeof v === "object");
  if (!entries.length) return <p className="text-xs text-slate-600">No ideal build defined.</p>;

  return (
    <div className="space-y-2">
      {entries.map(([key, comp]) => (
        <div key={key} className="bg-[#0a1220] border border-[#1e2d45] rounded-lg p-2.5">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-semibold text-slate-300">{COMPONENT_LABELS[key] ?? key.toUpperCase()}</span>
            <div className="flex items-center gap-2">
              <span className="text-xs text-[#00dc82]">Target £{comp.target_price}</span>
              <span className="text-xs text-slate-500">Walk-away £{comp.walk_away_price}</span>
            </div>
          </div>
          <div className="flex flex-wrap gap-1">
            {(comp.candidate_models ?? []).map(m => (
              <span key={m} className="text-[11px] bg-[#111c2e] border border-[#1e2d45] text-slate-400 px-1.5 py-0.5 rounded font-mono">{m}</span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 6: Rewrite the playbook card in `pc-flipper/app/playbooks/page.tsx`**

Replace the `PlaybookCard` component (currently around line 300-500) with a new version that uses the new components:

```tsx
import { SeasonalityChart } from "@/components/playbooks/SeasonalityChart";
import { ScoreBadges } from "@/components/playbooks/ScoreBadges";
import { IdealBuildPanel } from "@/components/playbooks/IdealBuildPanel";
```

Replace the `PlaybookCard` function:

```tsx
function PlaybookCard({ playbook, onEdit, onDelete, onActivate, onRetire, onRollback }: {
  playbook: Playbook;
  onEdit: (pb: Playbook) => void;
  onDelete: (id: number) => void;
  onActivate: (id: number) => void;
  onRetire: (id: number) => void;
  onRollback: (id: number) => void;
}) {
  const [tab, setTab] = useState<"overview" | "build" | "season">("overview");

  const pm = playbook.profit_model ?? {};
  const pricing = playbook.pricing_model ?? {};
  const hasProfit = pm.expected_profit && pm.expected_profit > 0;
  const hasBuildCost = pricing.expected_build_cost && pricing.expected_build_cost > 0;

  return (
    <div className="bg-[#0d1726] border border-[#1e2d45] rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-start justify-between px-4 pt-4 pb-3">
        <div className="flex items-start gap-3">
          <span className="text-2xl">{playbook.emoji}</span>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-slate-100 font-semibold text-sm">{playbook.name}</h3>
              <StatusBadge status={playbook.status as PlaybookStatus} />
            </div>
            {playbook.target_customer && (
              <p className="text-xs text-slate-500 mt-0.5">→ {playbook.target_customer}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1">
          {/* Rank score chip */}
          <span className="text-xs font-bold text-[#00dc82] bg-[#00dc82]/10 border border-[#00dc82]/20 px-2 py-0.5 rounded-full">
            #{Math.round(playbook.composite_rank_score)}
          </span>
          <button onClick={() => onEdit(playbook)} className="p-1.5 text-slate-500 hover:text-slate-200 hover:bg-white/5 rounded">
            <Pencil className="w-3.5 h-3.5" />
          </button>
          {playbook.status === "candidate" && (
            <button onClick={() => onActivate(playbook.id)} className="px-2 py-1 text-xs bg-[#00dc82]/10 text-[#00dc82] border border-[#00dc82]/20 rounded hover:bg-[#00dc82]/20">
              Activate
            </button>
          )}
          {playbook.status === "active" && (
            <button onClick={() => onRetire(playbook.id)} className="p-1.5 text-slate-500 hover:text-orange-400 hover:bg-white/5 rounded">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
          {playbook.status === "deprecated" && (
            <button onClick={() => onDelete(playbook.id)} className="p-1.5 text-slate-500 hover:text-red-400 hover:bg-white/5 rounded">
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Profit/cost summary bar */}
      {(hasProfit || hasBuildCost) && (
        <div className="flex items-center gap-4 px-4 py-2 bg-[#0a1220] border-y border-[#1e2d45]">
          {hasBuildCost && (
            <div>
              <div className="text-[11px] text-slate-500">Build cost</div>
              <div className="text-sm font-bold text-slate-300">
                £{pricing.minimum_build_cost?.toFixed(0) ?? "?"}–£{pricing.maximum_build_cost?.toFixed(0) ?? "?"}
              </div>
            </div>
          )}
          {hasProfit && (
            <div>
              <div className="text-[11px] text-slate-500">Profit range</div>
              <div className="text-sm font-bold text-[#00dc82]">
                £{pm.minimum_profit?.toFixed(0) ?? "?"}–£{pm.maximum_profit?.toFixed(0) ?? "?"}
              </div>
            </div>
          )}
          {pm.expected_roi_pct && pm.expected_roi_pct > 0 && (
            <div>
              <div className="text-[11px] text-slate-500">ROI</div>
              <div className="text-sm font-bold text-blue-400">{pm.expected_roi_pct.toFixed(0)}%</div>
            </div>
          )}
          {playbook.avg_days_to_sell != null && (
            <div className="ml-auto">
              <div className="text-[11px] text-slate-500">Avg sell time</div>
              <div className="text-sm font-bold text-slate-300">{playbook.avg_days_to_sell.toFixed(0)}d</div>
            </div>
          )}
        </div>
      )}

      {/* Tab nav */}
      <div className="flex gap-0 border-b border-[#1e2d45]">
        {(["overview", "build", "season"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              tab === t ? "text-[#00dc82] border-b-2 border-[#00dc82]" : "text-slate-500 hover:text-slate-300"
            }`}>
            {t === "overview" ? "Scores" : t === "build" ? "Ideal Build" : "Seasonality"}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="p-4">
        {tab === "overview" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <ScoreBadges playbook={playbook} />
            </div>
            <div>
              {playbook.what_they_use_it_for && (
                <div className="mb-3">
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest mb-1">What they use it for</div>
                  <p className="text-xs text-slate-400">{playbook.what_they_use_it_for}</p>
                </div>
              )}
              {playbook.critical_success_factors?.length > 0 && (
                <div>
                  <div className="text-[11px] font-semibold text-slate-500 uppercase tracking-widest mb-1">Critical success factors</div>
                  <ul className="space-y-0.5">
                    {playbook.critical_success_factors.map(f => (
                      <li key={f} className="text-xs text-slate-300 flex items-center gap-1.5">
                        <span className="w-1 h-1 bg-[#00dc82] rounded-full flex-shrink-0" />
                        {f}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}
        {tab === "build" && (
          <IdealBuildPanel idealBuild={playbook.ideal_build ?? {}} />
        )}
        {tab === "season" && (
          <SeasonalityChart seasonality={playbook.seasonality ?? {}} />
        )}
      </div>

      {/* Footer */}
      {playbook.last_reviewed && (
        <div className="px-4 py-2 border-t border-[#1e2d45]">
          <span className="text-[11px] text-slate-600">Last reviewed {relTime(playbook.last_reviewed)}</span>
        </div>
      )}
    </div>
  );
}
```

Also update the **header stats** to show composite rank leader and profit ranges. Replace the 4-stat grid in the main page:

```tsx
{/* Summary stats */}
<div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
  {[
    { label: "Active playbooks", value: active.length, color: "text-[#00dc82]", icon: <TrendingUp className="w-4 h-4" /> },
    { label: "Avg expected profit", value: active.length ? `£${Math.round(active.reduce((s,p) => s + (p.profit_model?.expected_profit ?? 0), 0) / active.length)}` : "—", color: "text-emerald-400", icon: <Target className="w-4 h-4" /> },
    { label: "Pending approvals", value: proposals.filter(p => p.status === "pending").length, color: "text-orange-400", icon: <AlertTriangle className="w-4 h-4" /> },
    { label: "Top ranked", value: active.sort((a,b) => b.composite_rank_score - a.composite_rank_score)[0]?.name?.split(" ")[0] ?? "—", color: "text-blue-400", icon: <Zap className="w-4 h-4" /> },
  ].map(item => (
    <Card key={item.label} className="glass-card">
      <CardContent className="p-4">
        <div className="flex items-center gap-2 text-slate-500 mb-1">
          {item.icon}
          <span className="text-xs">{item.label}</span>
        </div>
        <div className={`text-2xl font-bold ${item.color}`}>{item.value}</div>
      </CardContent>
    </Card>
  ))}
</div>
```

Add a **Seed** button next to the New Playbook button:

```tsx
<Button onClick={async () => { await api.playbooks.seed(); await load(); }}
  variant="outline" className="border-[#1e2d45] text-slate-400 hover:text-slate-200">
  Seed Playbooks
</Button>
```

- [ ] **Step 7: Rebuild frontend and verify**

```bash
docker compose build frontend && docker compose up -d frontend
```

Open http://andromeda-ts:4310/playbooks — should show 10 playbooks with score bars, seasonality charts and ideal build panels.

- [ ] **Step 8: Commit and push**

```bash
git add pc-flipper/lib/types.ts pc-flipper/lib/api.ts pc-flipper/app/playbooks/page.tsx \
  pc-flipper/components/playbooks/
git commit -m "feat: playbook dashboard with scores, seasonality chart, ideal build panel and ranking"
git push origin master
```

---

### Task 7: Wire up daily evolution in scheduler + verify end-to-end

**Files:**
- Verify: `pc-flipper-backend/app/workers/scheduler.py` (playbook_evolution job already registered)

- [ ] **Step 1: Confirm job is registered**

```bash
curl -s http://andromeda-ts:4311/api/schedule | python3 -c "
import json,sys; d=json.load(sys.stdin)
jobs = d.get('jobs', d) if isinstance(d, dict) else d
for j in jobs:
    if 'playbook' in str(j.get('id','')).lower():
        print(json.dumps(j, indent=2))
"
```

- [ ] **Step 2: Trigger manual evolution run via API**

```bash
curl -s -X POST "http://andromeda-ts:4311/api/schedule/trigger/playbook_evolution" | python3 -c "import json,sys; print(json.dumps(json.load(sys.stdin), indent=2))"
```

Expected: `{"ok": true, "playbooks_scored": 10, ...}`

- [ ] **Step 3: Verify ranked playbooks updated**

```bash
curl -s http://andromeda-ts:4311/api/playbooks/ranked | python3 -c "
import json,sys
pbs = json.load(sys.stdin)
print('Ranked playbooks:')
for i, p in enumerate(pbs, 1):
    print(f'  {i}. {p[\"emoji\"]} {p[\"name\"]} rank={p[\"composite_rank_score\"]} growth={p[\"market_growth_direction\"]}')
"
```

- [ ] **Step 4: Final commit and push**

```bash
git add -A
git commit -m "feat: Playbook Evolution System complete - 10 playbooks, 9-phase engine, rich dashboard"
git push origin master
```
