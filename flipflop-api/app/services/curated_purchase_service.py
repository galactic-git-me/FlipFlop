"""
Curated Purchase Plan Service.

Handles:
- Creating purchase plans from curated build orders
- Grouping components by vendor
- Linking inventory items
- Email-driven status updates (ordered → tracking → delivered → dispatched)
- Ad-hoc purchase tracking
- Build history gallery integration

Design:
- BuildBot provides primary + secondary vendor URLs and costs
- Email monitor updates status automatically
- Michael views shopping list in admin
- Analytics tracks from_inventory vs to_buy, expected vs actual costs
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from structlog import get_logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from app.models.curated_purchase_plan import (
    CuratedPurchasePlan,
    PurchasePlanComponentLine,
    PurchasePlanInventoryLink,
    AdHocPurchaseRecord,
    PurchasePlanStatus,
    ComponentLineStatus
)
from app.models.order import Order
from app.models.inventory import InventoryItem
from app.models.email_event import EmailEvent
from app.models.build import Build

log = get_logger(__name__)


class CuratedPurchaseService:
    """Service for managing curated build purchase plans."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_purchase_plan(
        self,
        order_id: int,
        curated_build_id: str,
        components_bom: List[Dict],
        admin_email: Optional[str] = None
    ) -> CuratedPurchasePlan:
        """
        Create purchase plan for a curated build order.
        
        Args:
            order_id: Order ID
            curated_build_id: Curated build ID (e.g., "FF-GVG-02")
            components_bom: List of component dicts with:
                - slot: Component slot (cpu, gpu, ram, etc.)
                - title: Component title
                - quantity: Quantity needed (default=1)
                - primary_vendor: Primary vendor name
                - primary_vendor_url: Clickable listing URL
                - primary_vendor_sku: Vendor SKU
                - primary_vendor_price_gbp: Unit price
                - secondary_vendor: Secondary vendor name (optional)
                - secondary_vendor_url: Secondary listing URL (optional)
                - secondary_vendor_sku: Secondary vendor SKU (optional)
                - secondary_vendor_price_gbp: Secondary unit price (optional)
                - spec: Component spec dict (optional)
            admin_email: Admin creating the plan
            
        Returns:
            Created CuratedPurchasePlan
        """
        log.info(
            "curated_purchase.create_plan_start",
            order_id=order_id,
            build_id=curated_build_id,
            components=len(components_bom)
        )
        
        # Check if purchase plan already exists
        stmt = select(CuratedPurchasePlan).where(
            CuratedPurchasePlan.order_id == order_id
        )
        result = await self.db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            log.warning("curated_purchase.plan_already_exists", order_id=order_id, plan_id=existing.id)
            return existing
        
        # Create purchase plan
        plan = CuratedPurchasePlan(
            order_id=order_id,
            curated_build_id=curated_build_id,
            status=PurchasePlanStatus.PENDING.value,
            total_components=len(components_bom)
        )
        
        self.db.add(plan)
        await self.db.flush()  # Get plan.id
        
        # Create component lines
        total_expected_cost = 0.0
        total_from_inventory = 0.0
        total_to_buy = 0.0
        components_from_inventory = 0
        components_to_buy = 0
        vendor_counts = {}
        
        for comp in components_bom:
            quantity = comp.get("quantity", 1)
            unit_price = comp.get("primary_vendor_price_gbp", 0.0)
            total_price = unit_price * quantity
            
            # Check if we have this component in inventory
            inventory_item = await self._find_inventory_match(comp.get("title"), comp.get("slot"))
            
            if inventory_item and inventory_item.quantity >= quantity:
                # Use from inventory
                source = "from_inventory"
                status = ComponentLineStatus.FROM_INVENTORY.value
                components_from_inventory += 1
                total_from_inventory += total_price
                
                # Reserve inventory
                await self._reserve_inventory(plan.id, inventory_item.id, quantity, comp.get("slot"))
            else:
                # Need to buy
                source = "to_buy"
                status = ComponentLineStatus.TO_BUY.value
                components_to_buy += 1
                total_to_buy += total_price
                
                # Count vendor
                vendor = comp.get("primary_vendor", "unknown")
                vendor_counts[vendor] = vendor_counts.get(vendor, 0) + 1
            
            # Create component line
            line = PurchasePlanComponentLine(
                purchase_plan_id=plan.id,
                component_slot=comp.get("slot"),
                component_title=comp.get("title"),
                component_spec=comp.get("spec"),
                quantity=quantity,
                expected_unit_price_gbp=unit_price,
                expected_total_price_gbp=total_price,
                primary_vendor_name=comp.get("primary_vendor", ""),
                primary_vendor_listing_url=comp.get("primary_vendor_url", ""),
                primary_vendor_sku=comp.get("primary_vendor_sku"),
                primary_vendor_price_gbp=unit_price,
                secondary_vendor_name=comp.get("secondary_vendor"),
                secondary_vendor_listing_url=comp.get("secondary_vendor_url"),
                secondary_vendor_sku=comp.get("secondary_vendor_sku"),
                secondary_vendor_price_gbp=comp.get("secondary_vendor_price_gbp"),
                status=status,
                source=source,
                inventory_item_id=inventory_item.id if inventory_item else None
            )
            
            self.db.add(line)
            total_expected_cost += total_price
        
        # Update plan totals
        plan.total_expected_cost_gbp = total_expected_cost
        plan.total_from_inventory_cost_gbp = total_from_inventory
        plan.total_to_buy_cost_gbp = total_to_buy
        plan.components_from_inventory = components_from_inventory
        plan.components_to_buy = components_to_buy
        plan.vendor_summary = vendor_counts
        
        # Determine primary vendor (most items from)
        if vendor_counts:
            primary_vendor = max(vendor_counts.items(), key=lambda x: x[1])[0]
            plan.primary_vendor = primary_vendor
        
        await self.db.commit()
        await self.db.refresh(plan)
        
        log.info(
            "curated_purchase.plan_created",
            plan_id=plan.id,
            order_id=order_id,
            from_inventory=components_from_inventory,
            to_buy=components_to_buy,
            expected_cost=total_expected_cost,
            primary_vendor=plan.primary_vendor
        )
        
        return plan
    
    async def _find_inventory_match(
        self,
        component_title: str,
        component_slot: Optional[str]
    ) -> Optional[InventoryItem]:
        """Find matching inventory item by title and type."""
        if not component_title:
            return None
        
        stmt = select(InventoryItem).where(
            and_(
                InventoryItem.component_name.ilike(f"%{component_title}%"),
                InventoryItem.quantity > 0
            )
        )
        
        if component_slot:
            stmt = stmt.where(InventoryItem.component_type == component_slot)
        
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def _reserve_inventory(
        self,
        plan_id: int,
        inventory_item_id: int,
        quantity: int,
        component_slot: Optional[str] = None
    ) -> PurchasePlanInventoryLink:
        """Reserve inventory item for purchase plan."""
        link = PurchasePlanInventoryLink(
            purchase_plan_id=plan_id,
            inventory_item_id=inventory_item_id,
            quantity_reserved=quantity,
            status="reserved"
        )
        
        self.db.add(link)
        await self.db.flush()
        
        log.info(
            "curated_purchase.inventory_reserved",
            plan_id=plan_id,
            inventory_id=inventory_item_id,
            quantity=quantity
        )
        
        return link
    
    async def process_order_confirmation_email(
        self,
        email_event_id: int,
        vendor_name: str,
        order_reference: str,
        items: List[Dict],
        total_cost: Optional[float] = None
    ) -> List[PurchasePlanComponentLine]:
        """
        Process order confirmation email and update component lines.
        
        Args:
            email_event_id: EmailEvent ID
            vendor_name: Vendor name from email
            order_reference: Order/reference number
            items: List of items in order (parsed from email)
            total_cost: Total cost from email (optional)
            
        Returns:
            Updated component lines
        """
        # Find component lines matching this vendor with status=to_buy
        stmt = select(PurchasePlanComponentLine).where(
            and_(
                PurchasePlanComponentLine.primary_vendor_name.ilike(f"%{vendor_name}%"),
                PurchasePlanComponentLine.status == ComponentLineStatus.TO_BUY.value
            )
        ).order_by(PurchasePlanComponentLine.created_at.desc())
        
        result = await self.db.execute(stmt)
        lines = result.scalars().all()
        
        updated_lines = []
        
        for line in lines:
            # Simple matching: if item title appears in email items
            # TODO: More sophisticated matching logic
            line.status = ComponentLineStatus.ORDERED.value
            line.order_confirmation_email_id = email_event_id
            line.order_date = datetime.utcnow()
            line.order_reference = order_reference
            
            updated_lines.append(line)
            
            # Update plan status
            await self._update_plan_status(line.purchase_plan_id)
        
        await self.db.commit()
        
        log.info(
            "curated_purchase.order_confirmed",
            email_id=email_event_id,
            vendor=vendor_name,
            lines_updated=len(updated_lines)
        )
        
        return updated_lines
    
    async def process_tracking_email(
        self,
        email_event_id: int,
        order_reference: Optional[str],
        tracking_number: str,
        courier: Optional[str] = None,
        expected_delivery: Optional[datetime] = None
    ) -> List[PurchasePlanComponentLine]:
        """Process tracking email and update component lines."""
        # Find component lines matching this order reference
        if order_reference:
            stmt = select(PurchasePlanComponentLine).where(
                PurchasePlanComponentLine.order_reference == order_reference
            )
        else:
            # Fall back to recent ordered items
            stmt = select(PurchasePlanComponentLine).where(
                PurchasePlanComponentLine.status == ComponentLineStatus.ORDERED.value
            ).order_by(PurchasePlanComponentLine.order_date.desc()).limit(10)
        
        result = await self.db.execute(stmt)
        lines = result.scalars().all()
        
        updated_lines = []
        
        for line in lines:
            line.status = ComponentLineStatus.TRACKING.value
            line.tracking_email_id = email_event_id
            line.tracking_number = tracking_number
            line.courier = courier
            line.expected_delivery_date = expected_delivery
            
            updated_lines.append(line)
            
            await self._update_plan_status(line.purchase_plan_id)
        
        await self.db.commit()
        
        log.info(
            "curated_purchase.tracking_added",
            email_id=email_event_id,
            tracking_number=tracking_number,
            lines_updated=len(updated_lines)
        )
        
        return updated_lines
    
    async def process_delivery_email(
        self,
        email_event_id: int,
        tracking_number: Optional[str] = None,
        order_reference: Optional[str] = None
    ) -> List[PurchasePlanComponentLine]:
        """Process delivery email and update component lines."""
        # Find component lines matching tracking number or order reference
        conditions = []
        if tracking_number:
            conditions.append(PurchasePlanComponentLine.tracking_number == tracking_number)
        if order_reference:
            conditions.append(PurchasePlanComponentLine.order_reference == order_reference)
        
        if not conditions:
            # Fall back to recent tracking items
            stmt = select(PurchasePlanComponentLine).where(
                PurchasePlanComponentLine.status == ComponentLineStatus.TRACKING.value
            ).order_by(PurchasePlanComponentLine.order_date.desc()).limit(10)
        else:
            stmt = select(PurchasePlanComponentLine).where(or_(*conditions))
        
        result = await self.db.execute(stmt)
        lines = result.scalars().all()
        
        updated_lines = []
        
        for line in lines:
            line.status = ComponentLineStatus.DELIVERED.value
            line.delivery_email_id = email_event_id
            line.delivery_date = datetime.utcnow()
            
            updated_lines.append(line)
            
            await self._update_plan_status(line.purchase_plan_id)
        
        await self.db.commit()
        
        # Check if plan is fully delivered → create inventory items
        for line in updated_lines:
            await self._check_and_create_inventory(line)
        
        log.info(
            "curated_purchase.delivered",
            email_id=email_event_id,
            lines_updated=len(updated_lines)
        )
        
        return updated_lines
    
    async def _check_and_create_inventory(self, line: PurchasePlanComponentLine):
        """Create inventory item from delivered component line if not already exists."""
        if line.source == "from_inventory":
            # Already from inventory, nothing to create
            return
        
        # Create inventory item
        inventory = InventoryItem(
            component_name=line.component_title,
            component_type=line.component_slot,
            quantity=line.quantity,
            base_price=line.actual_unit_price_gbp or line.expected_unit_price_gbp,
            shipping_cost=0.0,
            discount_amount=0.0,
            purchase_date=line.order_date or datetime.utcnow(),
            source=line.primary_vendor_name,
            notes=f"Ordered for curated build (plan #{line.purchase_plan_id})",
            marketplace=line.primary_vendor_name,
            listing_url=line.primary_vendor_listing_url,
            seller_name=line.primary_vendor_name,
            purchase_status="CONFIRMED",
            reconciliation_status="DELIVERED"
        )
        
        self.db.add(inventory)
        await self.db.flush()
        
        # Link to component line
        line.inventory_item_id = inventory.id
        
        await self.db.commit()
        
        log.info(
            "curated_purchase.inventory_created",
            line_id=line.id,
            inventory_id=inventory.id,
            component=line.component_title
        )
    
    async def _update_plan_status(self, plan_id: int):
        """Update purchase plan status based on component line statuses."""
        stmt = select(CuratedPurchasePlan).where(
            CuratedPurchasePlan.id == plan_id
        )
        result = await self.db.execute(stmt)
        plan = result.scalar_one_or_none()
        
        if not plan:
            return
        
        # Count component statuses
        lines_stmt = select(PurchasePlanComponentLine).where(
            PurchasePlanComponentLine.purchase_plan_id == plan_id
        )
        lines_result = await self.db.execute(lines_stmt)
        lines = lines_result.scalars().all()
        
        ordered_count = sum(1 for l in lines if l.status in [
            ComponentLineStatus.ORDERED.value,
            ComponentLineStatus.TRACKING.value,
            ComponentLineStatus.DELIVERED.value
        ])
        
        delivered_count = sum(1 for l in lines if l.status == ComponentLineStatus.DELIVERED.value)
        
        # Update plan counts
        plan.components_ordered = ordered_count
        plan.components_delivered = delivered_count
        
        # Update plan status
        if delivered_count == plan.total_components:
            plan.status = PurchasePlanStatus.FULLY_DELIVERED.value
            plan.all_delivered_at = datetime.utcnow()
            
            # Mark as build-ready
            for line in lines:
                if line.status == ComponentLineStatus.DELIVERED.value:
                    line.status = ComponentLineStatus.BUILD_READY.value
            
            plan.status = PurchasePlanStatus.BUILD_READY.value
            
        elif delivered_count > 0:
            plan.status = PurchasePlanStatus.PARTIALLY_DELIVERED.value
        elif ordered_count == plan.components_to_buy:
            plan.status = PurchasePlanStatus.FULLY_ORDERED.value
            plan.all_ordered_at = datetime.utcnow()
        elif ordered_count > 0:
            plan.status = PurchasePlanStatus.PARTIALLY_ORDERED.value
        
        await self.db.commit()
        
        log.info(
            "curated_purchase.plan_status_updated",
            plan_id=plan_id,
            status=plan.status,
            ordered=ordered_count,
            delivered=delivered_count
        )
    
    async def mark_dispatched(
        self,
        plan_id: int,
        build_id: Optional[int] = None,
        admin_email: Optional[str] = None
    ) -> CuratedPurchasePlan:
        """
        Mark purchase plan as dispatched (build completed and shipped).
        
        Archives inventory items and creates build history entry.
        """
        stmt = select(CuratedPurchasePlan).where(
            CuratedPurchasePlan.id == plan_id
        )
        result = await self.db.execute(stmt)
        plan = result.scalar_one_or_none()
        
        if not plan:
            raise ValueError(f"Purchase plan {plan_id} not found")
        
        # Update component lines
        lines_stmt = select(PurchasePlanComponentLine).where(
            PurchasePlanComponentLine.purchase_plan_id == plan_id
        )
        lines_result = await self.db.execute(lines_stmt)
        lines = lines_result.scalars().all()
        
        for line in lines:
            line.status = ComponentLineStatus.DISPATCHED.value
            line.used_in_build_at = datetime.utcnow()
        
        # Update inventory links
        links_stmt = select(PurchasePlanInventoryLink).where(
            PurchasePlanInventoryLink.purchase_plan_id == plan_id
        )
        links_result = await self.db.execute(links_stmt)
        links = links_result.scalars().all()
        
        for link in links:
            link.status = "dispatched"
            link.dispatched_at = datetime.utcnow()
            
            # Archive inventory item (reduce quantity)
            if link.inventory_item:
                link.inventory_item.quantity -= link.quantity_reserved
                if link.inventory_item.quantity < 0:
                    link.inventory_item.quantity = 0
        
        # Update plan
        plan.status = PurchasePlanStatus.COMPLETED.value
        plan.dispatched_at = datetime.utcnow()
        plan.build_completed_at = datetime.utcnow()
        
        if build_id:
            plan.specific_build_id = build_id
        
        await self.db.commit()
        
        log.info(
            "curated_purchase.dispatched",
            plan_id=plan_id,
            build_id=build_id,
            admin=admin_email
        )
        
        return plan
    
    async def get_shopping_list_grouped_by_vendor(
        self,
        plan_id: int
    ) -> Dict[str, List[Dict]]:
        """
        Get shopping list grouped by vendor for efficient shopping.
        
        Returns:
            {
                "vendor_name": [
                    {
                        "component": "AMD Ryzen 5 9600X",
                        "quantity": 1,
                        "expected_price": 199.99,
                        "listing_url": "https://...",
                        "secondary_vendor": "scan",
                        "secondary_url": "https://...",
                        "secondary_price": 204.99
                    }
                ]
            }
        """
        stmt = select(PurchasePlanComponentLine).where(
            and_(
                PurchasePlanComponentLine.purchase_plan_id == plan_id,
                PurchasePlanComponentLine.source == "to_buy",
                PurchasePlanComponentLine.status == ComponentLineStatus.TO_BUY.value
            )
        ).order_by(PurchasePlanComponentLine.primary_vendor_name.asc())
        
        result = await self.db.execute(stmt)
        lines = result.scalars().all()
        
        grouped = {}
        
        for line in lines:
            vendor = line.primary_vendor_name
            if vendor not in grouped:
                grouped[vendor] = []
            
            grouped[vendor].append({
                "component": line.component_title,
                "slot": line.component_slot,
                "quantity": line.quantity,
                "expected_price": line.expected_unit_price_gbp,
                "total_price": line.expected_total_price_gbp,
                "listing_url": line.primary_vendor_listing_url,
                "vendor_sku": line.primary_vendor_sku,
                "secondary_vendor": line.secondary_vendor_name,
                "secondary_url": line.secondary_vendor_listing_url,
                "secondary_price": line.secondary_vendor_price_gbp
            })
        
        return grouped
