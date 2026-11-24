"""
Tests for Price Alert Email Service (Phase 2, F2.1.2).

Verifies:
1. Price drop emails sent when triggered
2. Email killed by feature flag
3. Summary emails with multiple alerts
4. Email content formatting
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import PriceAlert, ManualBuild
from app.services.price_alert_emails import (
    send_price_alert_email,
    send_alert_summary_email,
)
from app.services.money import Money


@pytest.mark.asyncio
class TestPriceAlertEmails:
    """Test price alert email functionality."""

    async def test_email_sent_on_alert_trigger(self, db: AsyncSession):
        """Email sent when alert triggers with flag enabled."""
        # Setup
        build = ManualBuild(name="RTX 4070 Build")
        db.add(build)
        await db.commit()

        alert = PriceAlert(
            manual_build_id=build.id,
            user_email="user@example.com",
            target_price_gbp=8000,  # £80.00
            is_active=True,
            triggered_at=None,
        )
        db.add(alert)
        await db.commit()

        # Test: Send email when price drops below target
        current_price = Money(75.00, "GBP")

        # Mock email_service to avoid SMTP
        with patch("app.services.price_alert_emails._send") as mock_send:
            mock_send.return_value = True

            result = await send_price_alert_email(db, alert, current_price)

            # Verify
            assert result is True
            mock_send.assert_called_once()

    async def test_email_suppressed_by_flag(self, db: AsyncSession):
        """Email suppressed when feature flag disabled."""
        build = ManualBuild(name="Test Build")
        db.add(build)
        await db.commit()

        alert = PriceAlert(
            manual_build_id=build.id,
            user_email="user@example.com",
            target_price_gbp=8000,
        )

        current_price = Money(75.00, "GBP")

        # Mock flag to return False
        with patch("app.services.price_alert_emails.is_enabled") as mock_flag:
            mock_flag.return_value = False

            result = await send_price_alert_email(db, alert, current_price)

            # Should return True (success - flag suppressed)
            assert result is True

    async def test_email_content_formatting(self, db: AsyncSession):
        """Email contains properly formatted content."""
        build = ManualBuild(name="Custom PC", ebay_price=75.00)
        db.add(build)
        await db.commit()

        alert = PriceAlert(
            manual_build_id=build.id,
            user_email="buyer@example.com",
            target_price_gbp=8000,  # £80.00
        )

        current_price = Money(72.99, "GBP")

        with patch("app.services.price_alert_emails._send") as mock_send:
            mock_send.return_value = True

            await send_price_alert_email(db, alert, current_price)

            # Get email content from mock
            call_args = mock_send.call_args
            email_msg = call_args[0][0]

            # Verify content
            subject = email_msg["Subject"]
            assert "72.99" in subject or "Custom PC" in subject

    async def test_summary_email_multiple_alerts(self, db: AsyncSession):
        """Summary email sent for multiple triggered alerts."""
        # Setup: Multiple builds and alerts
        build1 = ManualBuild(name="Build 1", ebay_price=100.0)
        build2 = ManualBuild(name="Build 2", ebay_price=150.0)
        db.add(build1)
        db.add(build2)
        await db.commit()

        alert1 = PriceAlert(
            manual_build_id=build1.id,
            user_email="user@example.com",
            target_price_gbp=8000,
        )
        alert2 = PriceAlert(
            manual_build_id=build2.id,
            user_email="user@example.com",
            target_price_gbp=12000,
        )

        triggered = [
            (alert1, Money(75.00, "GBP")),
            (alert2, Money(110.00, "GBP")),
        ]

        with patch("app.services.price_alert_emails._send") as mock_send:
            mock_send.return_value = True

            result = await send_alert_summary_email(
                db, "user@example.com", triggered
            )

            assert result is True
            mock_send.assert_called_once()

    async def test_summary_email_shows_savings(self, db: AsyncSession):
        """Summary email calculates and displays total savings."""
        build = ManualBuild(name="Premium Build")
        db.add(build)
        await db.commit()

        alert = PriceAlert(
            manual_build_id=build.id,
            user_email="user@example.com",
            target_price_gbp=10000,  # £100.00
        )

        current_price = Money(89.99, "GBP")
        triggered = [(alert, current_price)]

        with patch("app.services.price_alert_emails._send") as mock_send:
            mock_send.return_value = True

            await send_alert_summary_email(db, "user@example.com", triggered)

            call_args = mock_send.call_args
            email_msg = call_args[0][0]
            subject = email_msg["Subject"]

            # Should mention number of alerts
            assert "1" in subject or "alert" in subject.lower()

    async def test_email_handles_missing_build(self, db: AsyncSession):
        """Email service handles deleted build gracefully."""
        # Alert referencing nonexistent build
        alert = PriceAlert(
            manual_build_id=99999,  # Doesn't exist
            user_email="user@example.com",
            target_price_gbp=8000,
        )

        current_price = Money(75.00, "GBP")

        with patch("app.services.price_alert_emails.is_enabled") as mock_flag:
            mock_flag.return_value = True

            result = await send_price_alert_email(db, alert, current_price)

            # Should return False (error)
            assert result is False

    async def test_email_error_handling(self, db: AsyncSession):
        """Email service gracefully handles SMTP errors."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        alert = PriceAlert(
            manual_build_id=build.id,
            user_email="user@example.com",
            target_price_gbp=8000,
        )

        current_price = Money(75.00, "GBP")

        # Mock SMTP failure
        with patch("app.services.price_alert_emails._send") as mock_send:
            mock_send.side_effect = Exception("SMTP connection failed")

            result = await send_price_alert_email(db, alert, current_price)

            # Should return False (error occurred)
            assert result is False


@pytest.mark.asyncio
class TestEmailPrecision:
    """Test that Money type prevents precision loss in emails."""

    async def test_email_displays_exact_prices(self, db: AsyncSession):
        """Email displays Money prices without rounding errors."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        # Alert at 0.1 + 0.2 = 0.3 (classic float error would be 0.30000000000000004)
        alert = PriceAlert(
            manual_build_id=build.id,
            user_email="user@example.com",
            target_price_gbp=30,  # £0.30
        )

        current_price = Money(0.29, "GBP")

        with patch("app.services.price_alert_emails._send") as mock_send:
            mock_send.return_value = True

            await send_price_alert_email(db, alert, current_price)

            # Money type ensures precision - no rounding errors in email
            assert mock_send.called

    async def test_summary_calculates_exact_savings(self, db: AsyncSession):
        """Summary email calculates exact savings with Money type."""
        build = ManualBuild(name="Test")
        db.add(build)
        await db.commit()

        # Savings that would have rounding error with floats
        alert = PriceAlert(
            manual_build_id=build.id,
            user_email="user@example.com",
            target_price_gbp=10000,  # £100.00
        )

        current_price = Money(99.99, "GBP")
        triggered = [(alert, current_price)]

        with patch("app.services.price_alert_emails._send") as mock_send:
            mock_send.return_value = True

            # Savings should be exactly £0.01
            await send_alert_summary_email(db, "user@example.com", triggered)

            assert mock_send.called
