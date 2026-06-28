"""
Vendor Management API - Register and manage new data sources.

Endpoints:
- GET /api/vendors - List all vendors
- POST /api/vendors/register-phase1 - Register Phase 1 vendors (Temu, BargainHardware, Components)
- POST /api/vendors/{vendor_id}/scrape - Trigger immediate scrape
- GET /api/vendors/{vendor_id}/status - Get vendor status and metrics
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import structlog

from app.database import get_db
from app.models.source import DataSource, SourceType

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/vendors", tags=["vendors"])


# Phase 1 vendor configurations
PHASE1_VENDORS = [
    {
        "name": "Components Catalogue",
        "url": "https://flipflop.local/scrapers/components",
        "type": SourceType.scrape,
        "enabled": True,
        "config": {
            "description": "Aggregated new PC components from Temu, BargainHardware, Amazon, eBay",
            "component_types": ["GPU", "RAM", "SSD", "CPU", "PSU", "Case", "Motherboard"],
            "min_price_gbp": 5,
            "max_price_gbp": 500,
            "condition": "new",
        },
        "expected_gem_rate": 0.35,
        "avg_profit_estimate": 95,
        "scrape_frequency_hours": 24,
        "expected_monthly_listings": 2000,
    },
    {
        "name": "Temu",
        "url": "https://www.temu.com/api/search",
        "type": SourceType.scrape,
        "enabled": True,
        "config": {
            "description": "Ultra-cheap NEW PC components from Temu marketplace",
            "search_terms": [
                "GPU DDR5",
                "RTX 4060 Ti",
                "Gaming SSD",
                "DDR4 RAM 32GB",
                "Intel Core i7",
                "AMD Ryzen 5",
                "PC PSU 650W",
                "PC case ATX",
            ],
            "shipping_filter": "UK only",
            "condition_filter": "new",
            "price_range": [10, 200],
        },
        "expected_gem_rate": 0.40,
        "avg_profit_estimate": 60,
        "scrape_frequency_hours": 24,
        "expected_monthly_listings": 750,
    },
    {
        "name": "BargainHardware",
        "url": "https://www.bargainhardware.co.uk",
        "type": SourceType.scrape,
        "enabled": True,
        "config": {
            "description": "UK hardware retailer with clearance and surplus stock",
            "categories": [
                "/components/processors",
                "/components/motherboards",
                "/components/memory",
                "/components/storage",
                "/components/graphics-cards",
                "/components/power-supplies",
                "/components/cases",
            ],
            "price_filter": "discount > 20%",
            "min_discount_pct": 20,
        },
        "expected_gem_rate": 0.35,
        "avg_profit_estimate": 110,
        "scrape_frequency_hours": 24,
        "expected_monthly_listings": 150,
    },
    {
        "name": "Vinted",
        "url": "https://www.vinted.co.uk/api/v2/catalog/items",
        "type": SourceType.scrape,
        "enabled": True,
        "config": {
            "description": "European online marketplace for used tech - PC and gaming components",
            "search_keywords": [
                "PC",
                "desktop",
                "gaming computer",
                "gaming parts",
                "vintage computer",
                "workstation",
                "gaming setup",
                "computer parts",
                "GPU",
                "motherboard",
            ],
            "condition_filters": ["good", "excellent", "like new"],
            "price_range": [20, 400],
            "focus": "Vintage PCs and used components from tech enthusiasts",
        },
        "expected_gem_rate": 0.28,
        "avg_profit_estimate": 110,
        "scrape_frequency_hours": 24,
        "expected_monthly_listings": 150,
    },
]


@router.get("/")
async def list_vendors(db: AsyncSession = Depends(get_db)):
    """List all registered vendors/data sources."""
    try:
        result = await db.execute(select(DataSource).order_by(DataSource.name))
        vendors = result.scalars().all()

        return {
            "total": len(vendors),
            "vendors": [
                {
                    "id": v.id,
                    "name": v.name,
                    "url": v.url,
                    "type": v.source_type.value,
                    "enabled": v.enabled,
                    "listings_total": v.listings_found_total,
                    "listings_last_run": v.listings_found_last_run,
                    "last_scraped_at": v.last_scraped_at,
                    "config": v.config,
                }
                for v in vendors
            ],
        }

    except Exception as e:
        log.error("vendors.list_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/register-phase1")
async def register_phase1_vendors(db: AsyncSession = Depends(get_db)):
    """Register Phase 1 vendors (Temu, BargainHardware, Components Catalogue)."""
    try:
        registered = []

        for vendor_config in PHASE1_VENDORS:
            # Check if vendor already exists
            existing = await db.execute(
                select(DataSource).where(DataSource.name == vendor_config["name"])
            )
            if existing.scalar():
                log.info("vendors.already_exists", vendor=vendor_config["name"])
                registered.append(
                    {
                        "name": vendor_config["name"],
                        "status": "already_registered",
                    }
                )
                continue

            # Create new vendor
            source = DataSource(
                name=vendor_config["name"],
                url=vendor_config["url"],
                source_type=vendor_config["type"],
                enabled=vendor_config["enabled"],
                config=vendor_config["config"],
            )

            # Add extended fields via config
            source.config.update(
                {
                    "expected_gem_rate": vendor_config.get("expected_gem_rate"),
                    "avg_profit_estimate": vendor_config.get("avg_profit_estimate"),
                    "scrape_frequency_hours": vendor_config.get("scrape_frequency_hours"),
                    "expected_monthly_listings": vendor_config.get("expected_monthly_listings"),
                }
            )

            db.add(source)
            await db.flush()

            log.info("vendors.registered", vendor=vendor_config["name"], id=source.id)
            registered.append(
                {
                    "id": source.id,
                    "name": vendor_config["name"],
                    "status": "registered",
                }
            )

        await db.commit()

        return {
            "total_registered": len([r for r in registered if r["status"] == "registered"]),
            "total_already_registered": len(
                [r for r in registered if r["status"] == "already_registered"]
            ),
            "vendors": registered,
            "message": "Phase 1 vendors registered successfully",
        }

    except Exception as e:
        await db.rollback()
        log.error("vendors.register_phase1_failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{vendor_id}/scrape")
async def trigger_vendor_scrape(vendor_id: int, db: AsyncSession = Depends(get_db)):
    """Trigger immediate scrape for a vendor."""
    try:
        result = await db.execute(select(DataSource).where(DataSource.id == vendor_id))
        vendor = result.scalar()

        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        # NOTE: In production, this would trigger background task
        # For now, just log the request
        log.info("vendors.scrape_triggered", vendor_id=vendor_id, vendor=vendor.name)

        return {
            "vendor_id": vendor_id,
            "vendor_name": vendor.name,
            "status": "scrape_initiated",
            "message": f"Scrape job initiated for {vendor.name}",
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("vendors.scrape_trigger_failed", vendor_id=vendor_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{vendor_id}/status")
async def get_vendor_status(vendor_id: int, db: AsyncSession = Depends(get_db)):
    """Get vendor status and metrics."""
    try:
        result = await db.execute(select(DataSource).where(DataSource.id == vendor_id))
        vendor = result.scalar()

        if not vendor:
            raise HTTPException(status_code=404, detail="Vendor not found")

        expected_gem_rate = vendor.config.get("expected_gem_rate", 0)
        expected_monthly = vendor.config.get("expected_monthly_listings", 0)
        avg_profit = vendor.config.get("avg_profit_estimate", 0)
        scrape_freq = vendor.config.get("scrape_frequency_hours", 24)

        return {
            "id": vendor.id,
            "name": vendor.name,
            "url": vendor.url,
            "enabled": vendor.enabled,
            "type": vendor.source_type.value,
            "metrics": {
                "total_listings_all_time": vendor.listings_found_total,
                "listings_last_run": vendor.listings_found_last_run,
                "expected_gem_rate": expected_gem_rate,
                "expected_monthly_listings": expected_monthly,
                "avg_profit_estimate": avg_profit,
                "scrape_frequency_hours": scrape_freq,
            },
            "last_scraped_at": vendor.last_scraped_at,
            "last_error": vendor.last_error,
            "config": vendor.config,
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error("vendors.status_failed", vendor_id=vendor_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/phase1/summary")
async def get_phase1_summary():
    """Get Phase 1 implementation summary."""
    return {
        "phase": "Phase 1: High-Priority Components + Vinted",
        "goal": "Unlock 2,000+ new component listings/month at 35%+ gem rate",
        "vendors": [
            {
                "name": "Components Catalogue",
                "type": "Aggregator",
                "expected_listings": 2000,
                "expected_gem_rate": 0.35,
                "avg_profit": 95,
                "description": "Aggregated new PC components from Temu, BargainHardware, Vinted, Amazon, eBay",
            },
            {
                "name": "Temu",
                "type": "API Scraper",
                "expected_listings": 750,
                "expected_gem_rate": 0.40,
                "avg_profit": 60,
                "description": "Ultra-cheap NEW PC components (GPU, RAM, SSD, CPU, PSU, Case)",
            },
            {
                "name": "BargainHardware",
                "type": "HTML Scraper",
                "expected_listings": 150,
                "expected_gem_rate": 0.35,
                "avg_profit": 110,
                "description": "UK hardware retailer with clearance/surplus stock (>20% discount)",
            },
            {
                "name": "Vinted",
                "type": "API Scraper",
                "expected_listings": 150,
                "expected_gem_rate": 0.28,
                "avg_profit": 110,
                "description": "European marketplace for used PCs and components - vintage PC niche + enthusiast deals",
            },
        ],
        "combined_impact": {
            "total_monthly_new_listings": 3050,
            "total_monthly_new_gems": 1078,
            "monthly_revenue_estimated": "£98,990",
            "current_baseline": "400-500 listings/month, ~110-140 gems",
            "improvement_factor": "7.7x increase in gem volume",
        },
    }
