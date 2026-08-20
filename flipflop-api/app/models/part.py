import enum
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, Text, Enum, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PartCategory(str, enum.Enum):
    ram = "ram"
    gpu = "gpu"
    ssd = "ssd"
    psu = "psu"
    case = "case"
    cpu = "cpu"
    motherboard = "motherboard"
    cooler = "cooler"
    accessory = "accessory"


class PartCondition(str, enum.Enum):
    new = "new"
    used = "used"
    refurb = "refurb"


class Part(Base):
    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    brand: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(200))
    category: Mapped[PartCategory] = mapped_column(Enum(PartCategory))
    specs: Mapped[str | None] = mapped_column(Text)

    # Where it was found
    source_site: Mapped[str | None] = mapped_column(String(100))   # "eBay", "Amazon", "Temu" etc.
    source_url: Mapped[str | None] = mapped_column(String(2000))   # direct link to listing/search
    condition: Mapped[PartCondition] = mapped_column(Enum(PartCondition), default=PartCondition.used)

    # Prices — updated by swarm
    price: Mapped[float | None] = mapped_column(Float)             # the found price
    price_new: Mapped[float | None] = mapped_column(Float)
    price_used: Mapped[float | None] = mapped_column(Float)
    price_refurb: Mapped[float | None] = mapped_column(Float)
    rrp: Mapped[float | None] = mapped_column(Float)               # Recommended Retail Price (shows discount %)

    image_url: Mapped[str | None] = mapped_column(String(2000))

    # For cases: sci-fi theme tag
    theme: Mapped[str | None] = mapped_column(String(100))

    # For cases: supported motherboard form factors (JSON array of: ATX, MATX, EATX, ITX, MINI_ITX)
    form_factors: Mapped[list[str] | None] = mapped_column(JSON)

    # For cases: extracted keywords (JSON array: gaming, dual-chamber, tempered-glass, RGB, wood, curved, fishtank, etc.)
    keywords: Mapped[list[str] | None] = mapped_column(JSON)

    # For cases: customer selection count (how many builds used this case)
    selection_count: Mapped[int] = mapped_column(Integer, default=0)

    # For cases: customer ratings & demand (from Amazon/reviews)
    rating: Mapped[float | None] = mapped_column(Float)  # 0-5 stars
    review_count: Mapped[int | None] = mapped_column(Integer)  # number of reviews
    sales_velocity: Mapped[str | None] = mapped_column(String(100))  # "50+ bought in past month"
    bestseller_rank: Mapped[int | None] = mapped_column(Integer)  # Amazon bestseller rank (1 = #1 bestseller)

    # Value it adds to resale
    resale_value_add: Mapped[float] = mapped_column(Float, default=0.0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_price_update: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # AI gem verification (populated asynchronously after rule-based scoring)
    claude_verdict:    Mapped[str | None]      = mapped_column(String(10))   # GEM | GOOD | REJECT
    claude_reasoning:  Mapped[str | None]      = mapped_column(Text)
    claude_confidence: Mapped[float | None]    = mapped_column(Float)
    claude_judged_at:  Mapped[datetime | None] = mapped_column(DateTime)

    def __repr__(self):
        return f"<Part {self.id} {self.name!r} {self.condition} £{self.price}>"
