"""
Curated Component Availability Service.

Handles:
- Live vendor availability checks (primary + backup SKUs)
- Automatic failover to backup when primary is OOS
- Build availability computation
- Shop visibility decisions
- Analytics tagging (sku_source=primary|backup)

Design:
- Daily FlipFlopXtension scrapes too slow alone
- Live vendor API checks (where available)
- Soft-swap to backup when primary OOS
- Never sell hard-OOS configuration
- Hide tier/ship until resolved if all SKUs OOS
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models.curated_component_sku import (
    CuratedComponentSKU,
    CuratedBuildAvailability,
    SKUSwapEvent,
    SKUAvailabilityStatus
)

log = get_logger(__name__)


class VendorAvailabilityChecker:
    """
    Abstract interface for vendor availability checks.
    
    Implementations for specific vendors (Overclockers, Scan, Amazon, etc.)
    should extend this and implement check_availability().
    
    This allows the system to work with or without live vendor integrations:
    - With integration: Real-time availability checks
    - Without integration: Fall back to extension scrape data
    """
    
    async def check_availability(
        self,
        vendor_sku: str,
        vendor_url: Optional[str] = None
    ) -> Tuple[SKUAvailabilityStatus, Optional[int]]:
        """
        Check availability for a vendor SKU.
        
        Args:
            vendor_sku: Vendor's product SKU/code
            vendor_url: Direct product page URL (optional)
            
        Returns:
            (status, estimated_stock_level)
            
        Status values:
        - IN_STOCK: Available for purchase
        - LOW_STOCK: Available but limited quantity
        - OUT_OF_STOCK: Not available
        - UNKNOWN: Could not determine
        - DISCONTINUED: No longer sold
        """
        # Default implementation returns UNKNOWN
        # Override this in vendor-specific implementations
        return SKUAvailabilityStatus.UNKNOWN, None


class ExtensionDataChecker(VendorAvailabilityChecker):
    """
    Fallback checker using FlipFlopXtension scrape data.
    
    When live vendor APIs aren't available, use the most recent
    extension observation for this SKU.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def check_availability(
        self,
        vendor_sku: str,
        vendor_url: Optional[str] = None
    ) -> Tuple[SKUAvailabilityStatus, Optional[int]]:
        """Check availability from extension scrape data."""
        # TODO: Query most recent GemRadarListingObservation or similar
        # for this SKU and parse availability status
        
        # Placeholder: return UNKNOWN if no data
        return SKUAvailabilityStatus.UNKNOWN, None


class CuratedAvailabilityService:
    """Service for managing curated build component availability."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.vendor_checkers: Dict[str, VendorAvailabilityChecker] = {
            "extension": ExtensionDataChecker(db),
            # Add vendor-specific checkers as they're implemented:
            # "overclockers": OverclockersChecker(),
            # "scan": ScanChecker(),
            # "amazon": AmazonChecker(),
        }
    
    async def check_sku_availability(
        self,
        sku: CuratedComponentSKU,
        force_refresh: bool = False
    ) -> Tuple[SKUAvailabilityStatus, Optional[int]]:
        """
        Check availability for a single SKU.
        
        Args:
            sku: The SKU to check
            force_refresh: Force a new check even if recently checked
            
        Returns:
            (status, estimated_stock_level)
        """
        # Skip check if recently checked (unless forced)
        if not force_refresh and sku.availability_checked_at:
            age = datetime.utcnow() - sku.availability_checked_at
            if age < timedelta(minutes=15):  # Cache for 15 minutes
                return SKUAvailabilityStatus(sku.availability_status), sku.estimated_stock_level
        
        # Get appropriate vendor checker
        vendor = sku.preferred_vendor or "extension"
        checker = self.vendor_checkers.get(vendor, self.vendor_checkers["extension"])
        
        # Check availability
        status, stock_level = await checker.check_availability(
            sku.vendor_sku or "",
            sku.vendor_url
        )
        
        # Update SKU record
        sku.availability_status = status.value
        sku.estimated_stock_level = stock_level
        sku.availability_checked_at = datetime.utcnow()
        sku.availability_check_source = vendor
        
        await self.db.commit()
        
        log.info(
            "curated_availability.sku_checked",
            build_id=sku.curated_build_id,
            slot=sku.component_slot,
            is_primary=sku.is_primary,
            status=status.value,
            stock_level=stock_level,
            vendor=vendor
        )
        
        return status, stock_level
    
    async def get_available_sku_for_slot(
        self,
        build_id: str,
        slot: str,
        check_live: bool = True
    ) -> Optional[CuratedComponentSKU]:
        """
        Get the best available SKU for a component slot.
        
        Priority:
        1. Primary SKU (if in stock)
        2. First backup (if primary OOS and backup in stock)
        3. Second backup (if all previous OOS)
        etc.
        
        Args:
            build_id: Curated build ID (e.g., "FF-GVG-02")
            slot: Component slot (e.g., "gpu")
            check_live: If True, check live availability; if False, use cached
            
        Returns:
            Best available SKU or None if all OOS
        """
        # Get all SKUs for this slot, ordered by priority
        stmt = (
            select(CuratedComponentSKU)
            .where(
                and_(
                    CuratedComponentSKU.curated_build_id == build_id,
                    CuratedComponentSKU.component_slot == slot,
                    CuratedComponentSKU.is_active == True
                )
            )
            .order_by(CuratedComponentSKU.priority.asc())
        )
        
        result = await self.db.execute(stmt)
        skus = result.scalars().all()
        
        if not skus:
            log.warning("curated_availability.no_skus", build_id=build_id, slot=slot)
            return None
        
        # Check each SKU in priority order
        for sku in skus:
            if check_live:
                status, _ = await self.check_sku_availability(sku)
            else:
                status = SKUAvailabilityStatus(sku.availability_status)
            
            # Return first in-stock or low-stock SKU
            if status in [SKUAvailabilityStatus.IN_STOCK, SKUAvailabilityStatus.LOW_STOCK]:
                return sku
        
        # All SKUs are OOS or unknown
        log.warning(
            "curated_availability.all_oos",
            build_id=build_id,
            slot=slot,
            checked_skus=len(skus)
        )
        return None
    
    async def update_build_availability(
        self,
        build_id: str,
        check_live: bool = True
    ) -> CuratedBuildAvailability:
        """
        Update overall availability status for a curated build.
        
        Checks all component slots and determines:
        - Is build sellable?
        - Which SKUs are active?
        - How many backups in use?
        - Should build be visible on shop?
        
        Args:
            build_id: Curated build ID
            check_live: Check live vendor availability
            
        Returns:
            Updated CuratedBuildAvailability record
        """
        slots = ["cpu", "motherboard", "ram", "gpu", "storage", "case", "psu", "cooling", "os"]
        
        components_status = {}
        active_skus = {}
        using_backup_count = 0
        backup_slots = []
        all_available = True
        
        # Check each component slot
        for slot in slots:
            sku = await self.get_available_sku_for_slot(build_id, slot, check_live)
            
            if sku:
                components_status[slot] = {
                    "status": sku.availability_status,
                    "is_primary": sku.is_primary,
                    "priority": sku.priority,
                    "component": sku.component_title
                }
                active_skus[slot] = {
                    "id": sku.id,
                    "title": sku.component_title,
                    "is_primary": sku.is_primary,
                    "sku_source": "primary" if sku.is_primary else "backup"
                }
                
                if not sku.is_primary:
                    using_backup_count += 1
                    backup_slots.append(slot)
            else:
                # No available SKU for this slot
                components_status[slot] = {
                    "status": "out_of_stock",
                    "is_primary": None,
                    "priority": None,
                    "component": None
                }
                all_available = False
        
        # Get or create availability record
        stmt = select(CuratedBuildAvailability).where(
            CuratedBuildAvailability.curated_build_id == build_id
        )
        result = await self.db.execute(stmt)
        availability = result.scalar_one_or_none()
        
        if not availability:
            availability = CuratedBuildAvailability(curated_build_id=build_id)
            self.db.add(availability)
        
        # Update availability record
        availability.is_available = all_available
        availability.availability_status = "available" if all_available else "out_of_stock"
        availability.components_status = components_status
        availability.active_skus = active_skus
        availability.using_backup_count = using_backup_count
        availability.backup_slots = backup_slots
        availability.last_checked_at = datetime.utcnow()
        availability.last_check_source = "system"
        availability.is_visible_on_shop = all_available
        availability.hidden_reason = None if all_available else "One or more components out of stock"
        
        await self.db.commit()
        await self.db.refresh(availability)
        
        log.info(
            "curated_availability.build_updated",
            build_id=build_id,
            is_available=all_available,
            using_backup_count=using_backup_count,
            backup_slots=backup_slots
        )
        
        return availability
    
    async def swap_sku(
        self,
        build_id: str,
        slot: str,
        from_sku_id: Optional[int],
        to_sku_id: int,
        reason: str,
        approved_by: Optional[str] = None,
        triggered_by_order_id: Optional[int] = None
    ) -> SKUSwapEvent:
        """
        Record a SKU swap event (primary → backup or vice versa).
        
        Args:
            build_id: Curated build ID
            slot: Component slot
            from_sku_id: SKU being replaced (None if initial)
            to_sku_id: SKU being activated
            reason: Swap reason (out_of_stock, price_change, manual, etc.)
            approved_by: Admin who approved (if manual swap)
            triggered_by_order_id: Order that triggered swap (if applicable)
            
        Returns:
            Created SKUSwapEvent
        """
        # Get SKU details for logging
        to_sku = await self.db.get(CuratedComponentSKU, to_sku_id)
        from_sku = await self.db.get(CuratedComponentSKU, from_sku_id) if from_sku_id else None
        
        # Create swap event
        swap = SKUSwapEvent(
            curated_build_id=build_id,
            component_slot=slot,
            from_sku_id=from_sku_id,
            to_sku_id=to_sku_id,
            swap_reason=reason,
            swap_source="admin" if approved_by else "system",
            availability_status_before=from_sku.availability_status if from_sku else None,
            availability_status_after=to_sku.availability_status if to_sku else None,
            approved_by=approved_by,
            triggered_by_order_id=triggered_by_order_id
        )
        
        self.db.add(swap)
        
        # Update build availability swap count
        stmt = select(CuratedBuildAvailability).where(
            CuratedBuildAvailability.curated_build_id == build_id
        )
        result = await self.db.execute(stmt)
        availability = result.scalar_one_or_none()
        
        if availability:
            availability.sku_swap_count += 1
            availability.last_sku_swap_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(swap)
        
        log.info(
            "curated_availability.sku_swapped",
            build_id=build_id,
            slot=slot,
            from_sku=from_sku.component_title if from_sku else None,
            to_sku=to_sku.component_title if to_sku else None,
            reason=reason,
            is_backup=not to_sku.is_primary if to_sku else None
        )
        
        return swap
    
    async def get_build_bom_with_availability(
        self,
        build_id: str,
        check_live: bool = False
    ) -> Dict:
        """
        Get complete BOM for a build with availability-aware SKU selection.
        
        Returns:
            {
                "build_id": "FF-GVG-02",
                "is_available": true,
                "components": {
                    "cpu": {
                        "title": "AMD Ryzen 5 9600X",
                        "sku_source": "primary",
                        "is_backup": false,
                        "availability_status": "in_stock",
                        ...
                    },
                    "gpu": {
                        "title": "AMD Radeon RX 9060 XT 16GB",
                        "sku_source": "backup",
                        "is_backup": true,
                        "availability_status": "in_stock",
                        "swapped_from": "NVIDIA GeForce RTX 5060 16GB",
                        ...
                    },
                    ...
                }
            }
        """
        availability = await self.update_build_availability(build_id, check_live)
        
        bom = {
            "build_id": build_id,
            "is_available": availability.is_available,
            "using_backup_count": availability.using_backup_count,
            "components": {}
        }
        
        for slot, sku_data in (availability.active_skus or {}).items():
            sku_id = sku_data.get("id")
            if sku_id:
                sku = await self.db.get(CuratedComponentSKU, sku_id)
                if sku:
                    bom["components"][slot] = {
                        "title": sku.component_title,
                        "sku_source": "primary" if sku.is_primary else "backup",
                        "is_backup": not sku.is_primary,
                        "availability_status": sku.availability_status,
                        "vendor": sku.preferred_vendor,
                        "vendor_sku": sku.vendor_sku,
                        "vendor_url": sku.vendor_url,
                        "checked_at": sku.availability_checked_at.isoformat() if sku.availability_checked_at else None
                    }
        
        return bom


# Convenience functions for common operations

async def check_all_builds_availability(db: AsyncSession, check_live: bool = True) -> Dict[str, bool]:
    """
    Check availability for all curated builds.
    
    Returns:
        Dict mapping build_id to is_available
    """
    service = CuratedAvailabilityService(db)
    
    # Get all unique build IDs
    stmt = select(CuratedComponentSKU.curated_build_id).distinct()
    result = await db.execute(stmt)
    build_ids = [row[0] for row in result.fetchall()]
    
    availability_map = {}
    for build_id in build_ids:
        availability = await service.update_build_availability(build_id, check_live)
        availability_map[build_id] = availability.is_available
    
    return availability_map


async def get_oos_builds(db: AsyncSession) -> List[str]:
    """
    Get list of build IDs that are currently out of stock.
    
    Returns:
        List of build IDs
    """
    stmt = select(CuratedBuildAvailability).where(
        CuratedBuildAvailability.is_available == False
    )
    result = await db.execute(stmt)
    availabilities = result.scalars().all()
    
    return [a.curated_build_id for a in availabilities]
