"""
Price Alert Email Service for Phase 2.

Sends notifications when price drops trigger alerts.
Gated by FEATURE_PRICE_ALERTS_EMAIL_ENABLED flag.

Pattern:
1. Alert triggered (check_and_trigger_alerts in price_alerts.py)
2. Email service called with alert details
3. Email killed by kill-switch if flag disabled
4. User receives notification with action links
"""

from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PriceAlert, ManualBuild
from app.services.email_service import send_email_async
from app.services.money import Money
from app.services.feature_flags import is_enabled, FeatureFlags
import structlog

log = structlog.get_logger(__name__)


async def send_price_alert_email(
    db: AsyncSession,
    alert: PriceAlert,
    current_price: Money,
) -> bool:
    """
    Send price drop notification email to user.

    Args:
        db: AsyncSession
        alert: PriceAlert that was triggered
        current_price: Current price (Money object)

    Returns:
        True if email sent or suppressed by flag, False on error
    """
    # Check if email feature is enabled
    if not is_enabled(FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED):
        log.info(
            "price_alert_email_suppressed_by_flag",
            alert_id=alert.id,
            user_email=alert.user_email,
        )
        return True  # Treat as success (flag prevented, not error)

    try:
        # Get build details
        build = await db.get(ManualBuild, alert.manual_build_id) if alert.manual_build_id else None
        if alert.alert_type != "component" and not build:
            log.error(
                "price_alert_email_build_not_found",
                alert_id=alert.id,
                build_id=alert.manual_build_id,
            )
            return False

        # Format prices for display
        target = Money.from_pennies(alert.target_price_gbp, "GBP")
        current_display = current_price.to_float()
        target_display = target.to_float()
        savings = (target_display - current_display) if current_display < target_display else 0

        # Build email content
        item_name = alert.component_key if alert.alert_type == "component" else build.name
        subject = f"Price Alert: {item_name} now £{current_display:.2f}"
        destination = "/sourcing" if alert.alert_type == "component" else f"/builds/{build.id}"

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Price Alert Triggered! 🎯</h2>

                <p>Good news! Your price alert for <strong>{item_name}</strong> has been triggered.</p>

                <div style="background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Current Price:</strong> £{current_display:.2f}</p>
                    <p><strong>Your Target:</strong> £{target_display:.2f}</p>
                    {f'<p><strong>Savings:</strong> £{savings:.2f}</strong></p>' if savings > 0 else ''}
                </div>

                <p>
                    <a href="https://flipflop.local{destination}"
                       style="display: inline-block; padding: 10px 20px; background-color: #007bff; color: white; text-decoration: none; border-radius: 5px;">
                        View matching listings
                    </a>
                </p>

                <p>
                    <small style="color: #666;">
                        This is an automated alert. You can manage your alerts in your account settings.
                    </small>
                </p>
            </body>
        </html>
        """

        # Send email
        await send_email_async(
            recipient=alert.user_email,
            subject=subject,
            html_body=html_body,
            reference=f"price_alert_{alert.id}",
        )

        log.info(
            "price_alert_email_sent",
            alert_id=alert.id,
            user_email=alert.user_email,
            build_id=build.id if build else None,
            current_price=current_display,
            target_price=target_display,
        )

        return True

    except Exception as e:
        log.error(
            "price_alert_email_failed",
            alert_id=alert.id,
            user_email=alert.user_email,
            error=str(e),
        )
        return False


async def send_alert_summary_email(
    db: AsyncSession,
    user_email: str,
    triggered_alerts: list[tuple[PriceAlert, Money]],
) -> bool:
    """
    Send batch summary email for multiple triggered alerts.

    Args:
        db: AsyncSession
        user_email: User's email
        triggered_alerts: List of (alert, current_price) tuples

    Returns:
        True if sent, False on error
    """
    if not is_enabled(FeatureFlags.PRICE_ALERTS_EMAIL_ENABLED):
        return True

    if not triggered_alerts:
        return True

    try:
        # Build alert list HTML
        alerts_html = ""
        total_savings = Money(0, "GBP")

        for alert, current_price in triggered_alerts:
            build = await db.get(ManualBuild, alert.manual_build_id)
            if not build:
                continue

            target = Money.from_pennies(alert.target_price_gbp, "GBP")
            current_display = current_price.to_float()
            target_display = target.to_float()

            if current_display < target_display:
                savings = target_display - current_display
                total_savings = total_savings + Money(savings, "GBP")

                alerts_html += f"""
                <tr>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">
                        <strong>{build.name}</strong>
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">
                        £{current_display:.2f}
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">
                        £{target_display:.2f}
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">
                        £{savings:.2f}
                    </td>
                    <td style="padding: 10px; border-bottom: 1px solid #ddd;">
                        <a href="https://flipflop.local/builds/{build.id}">View</a>
                    </td>
                </tr>
                """

        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif;">
                <h2>Price Alerts Summary 📊</h2>

                <p>Multiple price alerts have been triggered today!</p>

                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <thead>
                        <tr style="background-color: #f0f0f0;">
                            <th style="padding: 10px; text-align: left;">Build</th>
                            <th style="padding: 10px; text-align: left;">Current</th>
                            <th style="padding: 10px; text-align: left;">Target</th>
                            <th style="padding: 10px; text-align: left;">Savings</th>
                            <th style="padding: 10px; text-align: left;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {alerts_html}
                    </tbody>
                </table>

                <div style="background-color: #e8f5e9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Total Potential Savings: £{total_savings.to_float():.2f}</strong></p>
                </div>

                <p>
                    <small style="color: #666;">
                        This is an automated summary. You can manage your alerts in your account settings.
                    </small>
                </p>
            </body>
        </html>
        """

        subject = f"Price Alerts: {len(triggered_alerts)} builds on sale today!"

        await send_email_async(
            recipient=user_email,
            subject=subject,
            html_body=html_body,
            reference=f"price_alert_summary_{len(triggered_alerts)}",
        )

        log.info(
            "price_alert_summary_email_sent",
            user_email=user_email,
            alert_count=len(triggered_alerts),
            total_savings=total_savings.to_float(),
        )

        return True

    except Exception as e:
        log.error(
            "price_alert_summary_email_failed",
            user_email=user_email,
            error=str(e),
        )
        return False


async def send_email_async(
    recipient: str,
    subject: str,
    html_body: str,
    reference: str,
) -> bool:
    """
    Async wrapper around email service.

    For now, delegates to sync email_service.
    In production, would use async SMTP client.
    """
    # Import here to avoid circular imports
    from app.services.email_service import _send
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from app.config import get_settings

    settings = get_settings()

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from or "alerts@flipflop.co.uk"
        msg["To"] = recipient
        msg.attach(MIMEText(html_body, "html"))

        return _send(msg, reference)
    except Exception as e:
        log.error("async_email_wrapper_failed", error=str(e))
        return False
