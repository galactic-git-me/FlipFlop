"""
Price Alerts Service for Phase 2.

Enables users to set price-drop alerts on builds:
1. User sets target price (e.g., "notify me if price drops below £79.99")
2. Alert system monitors price changes
3. When price drops below target, send email notification
4. User can acknowledge/dismiss/re-arm alerts

Gated by feature flags:
- FEATURE_PRICE_ALERTS_RULES_ENABLED: enable alert rules engine
- FEATURE_PRICE_ALERTS_EMAIL_ENABLED: enable alert emails
"""

from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, update
from app.models import PriceAlert, PriceAlertEvent, ManualBuild
from app.services.money import Money
from app.services.feature_flags import is_enabled, FeatureFlags
import structlog

log = structlog.get_logger(__name__)


class PriceAlertError(Exception):
    """Price alert operation failed."""
    pass


class PriceAlertsService:
    """Manage user price alerts."""

    @staticmethod
    async def create_alert(
        db: AsyncSession,
        manual_build_id: int,
        user_email: str,
        target_price: Money,
    ) -> PriceAlert:
        """
        Create a new price alert for a user on a specific build.

        Args:
            db: AsyncSession
            manual_build_id: Build to monitor
            user_email: User's email address
            target_price: Money object with target price (GBP only)

        Returns:
            Created PriceAlert

        Raises:
            PriceAlertError: If build not found or invalid price
        """
        if target_price.currency != "GBP":
            raise PriceAlertError(f"Only GBP prices supported, got {target_price.currency}")

        # Verify build exists
        build = await db.get(ManualBuild, manual_build_id)
        if not build:
            raise PriceAlertError(f"Build {manual_build_id} not found")

        # Create alert (target_price stored as pennies)
        alert = PriceAlert(
            manual_build_id=manual_build_id,
            user_email=user_email,
            target_price_gbp=target_price.to_pennies(),
            monitoring_status="armed",
            is_active=True,
        )

        db.add(alert)
        await db.commit()

        log.info(
            "price_alert_created",
            alert_id=alert.id,
            build_id=manual_build_id,
            user_email=user_email,
            target_price=target_price.to_float(),
        )

        return alert

    @staticmethod
    async def list_active_alerts(
        db: AsyncSession,
        manual_build_id: int,
    ) -> list[PriceAlert]:
        """Get all active alerts for a build."""
        stmt = select(PriceAlert).where(
            and_(
                PriceAlert.manual_build_id == manual_build_id,
                PriceAlert.is_active.is_(True),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def check_and_trigger_alerts(
        db: AsyncSession,
        manual_build_id: int,
        current_price: Money,
    ) -> list[PriceAlert]:
        """
        Check if any active alerts should trigger on price drop.

        Called after price recalculation. If current_price < target_price,
        trigger the alert.

        Args:
            db: AsyncSession
            manual_build_id: Build whose price changed
            current_price: New price (Money object)

        Returns:
            List of alerts that were triggered
        """
        if not is_enabled(FeatureFlags.PRICE_ALERTS_RULES_ENABLED):
            return []

        if current_price.currency != "GBP":
            log.warning(
                "check_alerts_wrong_currency",
                currency=current_price.currency,
                build_id=manual_build_id,
            )
            return []

        # Get all active alerts for this build
        alerts = await PriceAlertsService.list_active_alerts(db, manual_build_id)

        triggered = []
        current_price_pennies = current_price.to_pennies()

        for alert in alerts:
            # Trigger if price dropped below target
            if current_price_pennies < alert.target_price_gbp:
                # Record trigger event
                event = PriceAlertEvent(
                    alert_id=alert.id,
                    event_type="triggered",
                    price_gbp=current_price_pennies,
                    notes=f"Price {Money.from_pennies(current_price_pennies, 'GBP')} dropped below target {Money.from_pennies(alert.target_price_gbp, 'GBP')}",
                )
                db.add(event)

                # Update alert
                alert.triggered_at = datetime.utcnow()
                alert.triggered_price_gbp = current_price_pennies
                alert.monitoring_status = "triggered"

                triggered.append(alert)
                log.info(
                    "price_alert_triggered",
                    alert_id=alert.id,
                    build_id=manual_build_id,
                    current_price=current_price.to_float(),
                    target_price=Money.from_pennies(alert.target_price_gbp, "GBP").to_float(),
                )

        if triggered:
            await db.commit()

        return triggered

    @staticmethod
    async def dismiss_alert(
        db: AsyncSession,
        alert_id: int,
    ) -> bool:
        """
        Dismiss an alert (user acknowledged and dismissed it).

        Args:
            db: AsyncSession
            alert_id: Alert to dismiss

        Returns:
            True if dismissed, False if not found
        """
        alert = await db.get(PriceAlert, alert_id)
        if not alert:
            return False

        alert.is_active = False
        alert.monitoring_status = "dismissed"

        event = PriceAlertEvent(
            alert_id=alert_id,
            event_type="dismissed",
            notes="User dismissed alert",
        )
        db.add(event)
        await db.commit()

        log.info("price_alert_dismissed", alert_id=alert_id)
        return True

    @staticmethod
    async def re_arm_alert(
        db: AsyncSession,
        alert_id: int,
    ) -> bool:
        """
        Re-arm a dismissed alert (user wants notifications again).

        Args:
            db: AsyncSession
            alert_id: Alert to re-arm

        Returns:
            True if re-armed, False if not found
        """
        alert = await db.get(PriceAlert, alert_id)
        if not alert:
            return False

        alert.is_active = True
        alert.triggered_at = None
        alert.triggered_price_gbp = None
        alert.triggered_listing_url = None
        alert.triggered_evidence_json = None
        alert.monitoring_status = "pending_evidence" if alert.alert_type == "component" and alert.cpk else "pending_identity" if alert.alert_type == "component" else "armed"

        event = PriceAlertEvent(
            alert_id=alert_id,
            event_type="re_armed",
            notes="User re-armed alert",
        )
        db.add(event)
        await db.commit()

        log.info("price_alert_re_armed", alert_id=alert_id)
        return True

    @staticmethod
    async def get_alert_history(
        db: AsyncSession,
        alert_id: int,
    ) -> list[PriceAlertEvent]:
        """Get all events for an alert (audit trail)."""
        stmt = select(PriceAlertEvent).where(
            PriceAlertEvent.alert_id == alert_id
        ).order_by(PriceAlertEvent.created_at.desc())
        result = await db.execute(stmt)
        return result.scalars().all()
