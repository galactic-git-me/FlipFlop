"""Quote generation service for budget-based PC build recommendations."""
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, Dict, List, Any
from decimal import Decimal

from app.models.component_catalogue import Component

log = structlog.get_logger(__name__)

# Budget tier definitions with recommended component types
BUDGET_TIERS = {
    800: {
        "name": "Budget Gaming",
        "cpu": "Ryzen 5 5600X",
        "gpu": "RTX 3060",
        "ram": "16GB DDR4",
        "ssd": "500GB NVMe",
        "motherboard": "B550",
        "psu": "650W Gold",
        "cooler": "Stock Cooler",
        "case": "Mid Tower",
    },
    1200: {
        "name": "Mid-Range Gaming",
        "cpu": "Ryzen 5 5600X",
        "gpu": "RTX 3070",
        "ram": "16GB DDR5",
        "ssd": "1TB NVMe",
        "motherboard": "B850",
        "psu": "750W Gold",
        "cooler": "Noctua NH-D15",
        "case": "Mid Tower",
    },
    1500: {
        "name": "High-End Gaming",
        "cpu": "Ryzen 7 5800X3D",
        "gpu": "RTX 4070",
        "ram": "32GB DDR5",
        "ssd": "1TB NVMe",
        "motherboard": "B850",
        "psu": "850W Gold",
        "cooler": "Noctua NH-D15",
        "case": "Full Tower",
    },
    2000: {
        "name": "Workstation",
        "cpu": "Ryzen 7 7800X3D",
        "gpu": "RTX 4080",
        "ram": "64GB DDR5",
        "ssd": "2TB NVMe",
        "motherboard": "X870",
        "psu": "1000W Gold",
        "cooler": "Custom Loop",
        "case": "Full Tower",
    },
    3000: {
        "name": "High-End Workstation",
        "cpu": "Ryzen 9 7950X",
        "gpu": "RTX 6000",
        "ram": "128GB DDR5",
        "ssd": "4TB NVMe",
        "motherboard": "X870E",
        "psu": "1200W Platinum",
        "cooler": "Custom Loop",
        "case": "Server Case",
    },
}

# Component category mappings
COMPONENT_CATEGORY_MAP = {
    "cpu": "CPU",
    "gpu": "GPU",
    "ram": "Memory",
    "ssd": "Storage",
    "motherboard": "Motherboard",
    "psu": "Power Supply",
    "cooler": "CPU Cooler",
    "case": "Computer Case",
}

# Labor and overhead costs
LABOR_COST_PER_HOUR = Decimal("25.00")
LABOR_HOURS_PER_BUILD = Decimal("3.5")
OVERHEAD_PERCENTAGE = Decimal("0.10")  # 10% overhead

# Fallback pricing if components not found in database
FALLBACK_PRICES = {
    "CPU": Decimal("250.00"),
    "GPU": Decimal("400.00"),
    "Memory": Decimal("100.00"),
    "Storage": Decimal("80.00"),
    "Motherboard": Decimal("150.00"),
    "Power Supply": Decimal("120.00"),
    "CPU Cooler": Decimal("50.00"),
    "Computer Case": Decimal("100.00"),
}


class QuoteService:
    """Service for generating PC build quotes based on customer budget."""

    @staticmethod
    def get_budget_tiers() -> Dict[int, Dict[str, Any]]:
        """
        Get all available budget tiers with their specs.

        Returns:
            Dictionary mapping budget amounts to tier specifications.
        """
        return BUDGET_TIERS

    @staticmethod
    def find_closest_budget_tier(budget: float) -> Optional[int]:
        """
        Find the closest budget tier for a given budget.

        Args:
            budget: Customer budget in GBP.

        Returns:
            The budget tier amount, or None if budget is outside valid range.
        """
        budget = float(budget)

        # Validate budget is in acceptable range
        min_budget = min(BUDGET_TIERS.keys())
        max_budget = max(BUDGET_TIERS.keys())

        if budget < min_budget or budget > max_budget:
            return None

        # Find closest tier
        tiers = sorted(BUDGET_TIERS.keys())
        closest_tier = min(tiers, key=lambda x: abs(x - budget))
        return closest_tier

    @staticmethod
    def get_recommended_specs(budget: float) -> Optional[Dict[str, str]]:
        """
        Get recommended component specs for a given budget.

        Args:
            budget: Customer budget in GBP.

        Returns:
            Dictionary of recommended component specs, or None if budget out of range.
        """
        closest_tier = QuoteService.find_closest_budget_tier(budget)
        if closest_tier is None:
            return None

        return BUDGET_TIERS[closest_tier].copy()

    @staticmethod
    async def calculate_component_costs(
        db: AsyncSession,
        specs: Dict[str, str],
    ) -> tuple[Dict[str, Any], Decimal]:
        """
        Calculate component costs from database prices.

        Args:
            db: Database session.
            specs: Dictionary of component specs (keys like 'cpu', 'gpu', etc).

        Returns:
            Tuple of (components list with prices, total parts cost).
        """
        components: List[Dict[str, Any]] = []
        total_parts_cost = Decimal("0.00")

        # Iterate through spec items and find matching components
        for spec_key, spec_value in specs.items():
            if spec_key == "name":  # Skip tier name
                continue

            category = COMPONENT_CATEGORY_MAP.get(spec_key)
            if not category:
                log.warning("Unknown component type", component_type=spec_key)
                continue

            # Try to find component in database matching spec
            price = await QuoteService._find_component_price(
                db, category, spec_value
            )

            if price is None:
                # Use fallback pricing
                price = FALLBACK_PRICES.get(category, Decimal("100.00"))
                log.warning(
                    "Using fallback price",
                    component_type=spec_key,
                    category=category,
                    fallback_price=float(price),
                )

            components.append({
                "component_type": spec_key,
                "component_category": category,
                "component_name": spec_value,
                "price": float(price),
                "quantity": 1,
            })

            total_parts_cost += price

        return components, total_parts_cost

    @staticmethod
    async def _find_component_price(
        db: AsyncSession,
        category: str,
        search_term: str,
    ) -> Optional[Decimal]:
        """
        Search database for component price matching category and search term.

        Args:
            db: Database session.
            category: Component category (e.g., "CPU", "GPU").
            search_term: Search term to match (e.g., "Ryzen 5 5600X").

        Returns:
            Component price as Decimal, or None if not found.
        """
        try:
            # Search for components matching category and model name
            stmt = select(Component).where(
                Component.category == category
            ).limit(1)

            # If we have a search term, try to match on model
            if search_term and search_term.lower() != "stock cooler":
                stmt = select(Component).where(
                    (Component.category == category)
                    & (Component.model.ilike(f"%{search_term}%"))
                ).limit(1)

            result = await db.execute(stmt)
            component = result.scalar_one_or_none()

            if component and component.market_price:
                return Decimal(str(component.market_price))

            return None
        except Exception as e:
            log.error(
                "Error searching for component price",
                category=category,
                search_term=search_term,
                error=str(e),
            )
            return None

    @staticmethod
    async def generate_quote(
        budget: float,
        db: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a complete quote for a given budget.

        Args:
            budget: Customer budget in GBP (800-3000).
            db: Database session.

        Returns:
            Quote dictionary with breakdown, or None if budget invalid.
        """
        # Validate budget and get specs
        specs = QuoteService.get_recommended_specs(budget)
        if specs is None:
            return None

        # Get component tier name and remove it from specs for pricing
        tier_name = specs.pop("name")

        # Calculate component costs
        components, parts_cost = await QuoteService.calculate_component_costs(
            db, specs
        )

        # Calculate labor costs
        labor_cost = LABOR_COST_PER_HOUR * LABOR_HOURS_PER_BUILD

        # Calculate overhead (10% of parts + labor)
        subtotal = parts_cost + labor_cost
        overhead_cost = subtotal * OVERHEAD_PERCENTAGE

        # Calculate total
        total_price = subtotal + overhead_cost

        # Build quote response
        quote = {
            "budget": float(budget),
            "tier_name": tier_name,
            "recommended_specs": specs,
            "components": components,
            "parts_cost_total": float(parts_cost),
            "labor_cost": float(labor_cost),
            "overhead_cost": float(overhead_cost),
            "subtotal": float(subtotal),
            "total_price": float(total_price),
            "estimated_build_days": 7,
            "budget_remaining": float(Decimal(str(budget)) - total_price),
            "within_budget": total_price <= Decimal(str(budget)),
        }

        return quote
