"""
Components Aggregator - Aggregate NEW components from multiple sources

Target: Temu + BargainHardware + Amazon + eBay sub-£30 items
Expected: 2,000+ listings/month at 35-40% gem rate
Strategy: Aggregate sources into unified "Components Catalogue"
Component types: GPU, RAM, SSD, CPU, PSU, Case, Motherboard, Cooling
"""

import asyncio
import structlog
from datetime import datetime
from typing import Optional, List
from enum import Enum

log = structlog.get_logger(__name__)


class ComponentType(str, Enum):
    """PC component types."""

    GPU = "GPU"
    RAM = "RAM"
    SSD = "SSD"
    NVME = "NVMe"
    CPU = "CPU"
    PSU = "PSU"
    CASE = "Case"
    MOTHERBOARD = "Motherboard"
    COOLING = "Cooling"
    OTHER = "Other"


class ComponentSource(str, Enum):
    """Component source vendors."""

    TEMU = "Temu"
    BARGAIN_HARDWARE = "BargainHardware"
    VINTED = "Vinted"
    AMAZON = "Amazon"
    EBAY = "eBay"
    ALIEXPRESS = "AliExpress"


class ComponentAggregatorConfig:
    """Configuration for Components Aggregator."""

    # Data quality requirements
    min_price_gbp = 5
    max_price_gbp = 500
    condition_filter = "new"  # Only new/unused components

    # Source preferences
    sources_priority = [
        ComponentSource.TEMU,
        ComponentSource.BARGAIN_HARDWARE,
        ComponentSource.VINTED,
        ComponentSource.AMAZON,
        ComponentSource.EBAY,
    ]

    # Scraping config
    scrape_frequency_hours = 24
    expected_monthly_listings = 2000
    expected_gem_rate = 0.37
    avg_profit_estimate = 95  # £40-£150 range average


class AggregatedComponent:
    """Represents an aggregated component listing."""

    def __init__(self, **kwargs):
        self.title = kwargs.get("title", "")
        self.source = kwargs.get("source", "")
        self.source_url = kwargs.get("source_url", "")
        self.price_gbp = kwargs.get("price_gbp", 0)
        self.shipping_cost_gbp = kwargs.get("shipping_cost_gbp", 0)
        self.condition = kwargs.get("condition", "new")
        self.component_type = kwargs.get("component_type", ComponentType.OTHER)
        self.component_model = kwargs.get("component_model")
        self.seller = kwargs.get("seller", "")
        self.seller_rating = kwargs.get("seller_rating", 0)
        self.in_stock = kwargs.get("in_stock", True)
        self.discount_pct = kwargs.get("discount_pct", 0)
        self.fetched_at = kwargs.get("fetched_at", datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "title": self.title,
            "source": self.source,
            "source_url": self.source_url,
            "price_gbp": self.price_gbp,
            "shipping_cost_gbp": self.shipping_cost_gbp,
            "total_cost_gbp": self.price_gbp + self.shipping_cost_gbp,
            "condition": self.condition,
            "component_type": self.component_type.value,
            "component_model": self.component_model,
            "seller": self.seller,
            "seller_rating": self.seller_rating,
            "in_stock": self.in_stock,
            "discount_pct": self.discount_pct,
            "fetched_at": self.fetched_at,
        }

    def is_valid(self) -> bool:
        """Check if component meets quality standards."""
        # Must have title and price
        if not self.title or self.price_gbp <= 0:
            return False

        # Price must be in acceptable range
        total_cost = self.price_gbp + self.shipping_cost_gbp
        if total_cost < ComponentAggregatorConfig.min_price_gbp:
            return False
        if total_cost > ComponentAggregatorConfig.max_price_gbp:
            return False

        # Must be new condition
        if self.condition.lower() not in ["new", "unused", "factory sealed"]:
            return False

        # Must be in stock
        if not self.in_stock:
            return False

        return True


async def aggregate_components() -> dict:
    """
    Aggregate NEW PC components from all sources.

    Returns:
        dict with 'listings' (list) and 'stats' (dict)
    """
    log.info("components_aggregator.starting", sources=len(ComponentAggregatorConfig.sources_priority))

    all_components = []
    stats = {
        "total_fetched": 0,
        "valid": 0,
        "invalid": 0,
        "by_type": {},
        "by_source": {},
        "errors": [],
    }

    try:
        # Aggregate from all configured sources (LIVE DATA ONLY)
        # Calls actual scraper functions for each source
        for source in ComponentAggregatorConfig.sources_priority:
            try:
                # Import and call source-specific scraper
                if source == ComponentSource.TEMU:
                    from app.scrapers.temu_scraper import scrape_temu_components

                    result = await scrape_temu_components()
                    components = _convert_temu_to_components(result.get("listings", []))

                elif source == ComponentSource.BARGAIN_HARDWARE:
                    from app.scrapers.bargain_hardware_scraper import (
                        scrape_bargain_hardware_components,
                    )

                    result = await scrape_bargain_hardware_components()
                    components = _convert_bh_to_components(result.get("listings", []))

                elif source == ComponentSource.VINTED:
                    from app.scrapers.vinted_scraper import scrape_vinted_tech

                    result = await scrape_vinted_tech()
                    components = _convert_vinted_to_components(result.get("listings", []))

                else:
                    # Placeholder for other sources
                    log.info("components_aggregator.source_not_implemented", source=source.value)
                    continue

                # Validate and add to collection
                for component in components:
                    if component.is_valid():
                        all_components.append(component.to_dict())
                        stats["valid"] += 1

                        # Track by type
                        ctype = component.component_type.value
                        stats["by_type"][ctype] = stats["by_type"].get(ctype, 0) + 1

                    else:
                        stats["invalid"] += 1

                    stats["total_fetched"] += 1

                # Track by source
                stats["by_source"][source.value] = len([c for c in components if c.is_valid()])

            except Exception as e:
                log.error(
                    "components_aggregator.source_error", source=source.value, error=str(e)
                )
                stats["errors"].append({"source": source.value, "error": str(e)})

        log.info(
            "components_aggregator.complete",
            total_fetched=stats["total_fetched"],
            valid=stats["valid"],
            by_type=stats["by_type"],
        )

        return {
            "source": "Components Catalogue",
            "listings": all_components,
            "stats": stats,
            "fetched_at": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        log.error("components_aggregator.failed", error=str(e))
        raise


def _convert_temu_to_components(temu_listings: List[dict]) -> List[AggregatedComponent]:
    """Convert Temu scraper output to AggregatedComponent objects."""
    components = []

    for listing in temu_listings:
        try:
            component = AggregatedComponent(
                title=listing.get("title", ""),
                source=ComponentSource.TEMU.value,
                source_url=listing.get("source_url", ""),
                price_gbp=listing.get("price_gbp", 0),
                shipping_cost_gbp=listing.get("shipping_cost_gbp", 0),
                condition=listing.get("condition", "new"),
                component_type=_parse_component_type(listing.get("category", "")),
                component_model=listing.get("component_type"),
                seller=listing.get("seller", ""),
                seller_rating=listing.get("rating", 0),
                in_stock=True,
                discount_pct=0,  # Temu doesn't track original prices
            )
            components.append(component)
        except Exception as e:
            log.debug("components_aggregator.temu_conversion_error", error=str(e))
            continue

    return components


def _convert_bh_to_components(bh_listings: List[dict]) -> List[AggregatedComponent]:
    """Convert BargainHardware scraper output to AggregatedComponent objects."""
    components = []

    for listing in bh_listings:
        try:
            component = AggregatedComponent(
                title=listing.get("title", ""),
                source=ComponentSource.BARGAIN_HARDWARE.value,
                source_url=listing.get("source_url", ""),
                price_gbp=listing.get("price_gbp", 0),
                shipping_cost_gbp=0,  # BargainHardware usually includes shipping
                condition="new",
                component_type=_parse_component_type(listing.get("category", "")),
                component_model=listing.get("component_type"),
                seller="BargainHardware",
                seller_rating=4.5,  # Default good rating
                in_stock=listing.get("in_stock", True),
                discount_pct=listing.get("discount_pct", 0),
            )
            components.append(component)
        except Exception as e:
            log.debug("components_aggregator.bh_conversion_error", error=str(e))
            continue

    return components


def _convert_vinted_to_components(vinted_listings: List[dict]) -> List[AggregatedComponent]:
    """Convert Vinted scraper output to AggregatedComponent objects."""
    components = []

    for listing in vinted_listings:
        try:
            component = AggregatedComponent(
                title=listing.get("title", ""),
                source=ComponentSource.VINTED.value,
                source_url=listing.get("source_url", ""),
                price_gbp=listing.get("price_gbp", 0),
                shipping_cost_gbp=0,  # Vinted shipping varies, typically negotiated
                condition=listing.get("condition", "good"),
                component_type=_parse_component_type(listing.get("category", "")),
                component_model=listing.get("component_type"),
                seller=listing.get("seller", "Vinted User"),
                seller_rating=listing.get("seller_rating", 0),
                in_stock=True,  # Vinted listings are always active
                discount_pct=0,  # Used items, no discount applicable
            )
            components.append(component)
        except Exception as e:
            log.debug("components_aggregator.vinted_conversion_error", error=str(e))
            continue

    return components


def _parse_component_type(category_str: str) -> ComponentType:
    """Parse category string to ComponentType enum."""
    category_lower = category_str.lower()

    if "gpu" in category_lower or "graphics" in category_lower:
        return ComponentType.GPU
    elif "ram" in category_lower or "memory" in category_lower:
        return ComponentType.RAM
    elif "nvme" in category_lower or "m.2" in category_lower:
        return ComponentType.NVME
    elif "ssd" in category_lower or "storage" in category_lower:
        return ComponentType.SSD
    elif "cpu" in category_lower or "processor" in category_lower:
        return ComponentType.CPU
    elif "psu" in category_lower or "power" in category_lower:
        return ComponentType.PSU
    elif "case" in category_lower or "chassis" in category_lower:
        return ComponentType.CASE
    elif "motherboard" in category_lower or "mobo" in category_lower:
        return ComponentType.MOTHERBOARD
    elif "cooling" in category_lower or "fan" in category_lower or "heatsink" in category_lower:
        return ComponentType.COOLING
    else:
        return ComponentType.OTHER


async def get_components_catalogue_status() -> dict:
    """Get aggregator status and configuration."""
    return {
        "source": "Components Catalogue",
        "enabled": True,
        "expected_listings_per_month": ComponentAggregatorConfig.expected_monthly_listings,
        "expected_gem_rate": ComponentAggregatorConfig.expected_gem_rate,
        "avg_profit_estimate": ComponentAggregatorConfig.avg_profit_estimate,
        "scrape_frequency_hours": ComponentAggregatorConfig.scrape_frequency_hours,
        "component_types": len(ComponentType),
        "source_priority": [s.value for s in ComponentAggregatorConfig.sources_priority],
        "quality_requirements": {
            "condition": "new only",
            "in_stock": True,
            "price_range_gbp": [
                ComponentAggregatorConfig.min_price_gbp,
                ComponentAggregatorConfig.max_price_gbp,
            ],
        },
    }
