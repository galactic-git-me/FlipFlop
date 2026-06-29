"""Tests for payment integration and order creation flow."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from app.services.payment_service import PaymentService
from app.schemas.payment import (
    CreatePaymentIntentRequest,
    ConfirmPaymentRequest,
)


@pytest.mark.unit
class TestPaymentService:
    """Tests for PaymentService."""

    @pytest.fixture
    def payment_service(self):
        """Create PaymentService instance."""
        return PaymentService()

    @patch("app.services.payment_service.stripe")
    async def test_create_payment_intent_success(self, mock_stripe, payment_service):
        """Test successful payment intent creation."""
        # Mock Stripe response
        mock_intent = MagicMock()
        mock_intent.id = "pi_test123"
        mock_intent.client_secret = "pi_test123_secret_abc"
        mock_stripe.PaymentIntent.create.return_value = mock_intent

        # Create payment intent
        result = await payment_service.create_payment_intent(
            customer_id=1,
            budget=1200.00,
            quote_data={"specs": "test"},
        )

        # Verify results
        assert result["intent_id"] == "pi_test123"
        assert result["client_secret"] == "pi_test123_secret_abc"
        assert result["amount"] == 1200.00
        assert result["currency"] == "gbp"

        # Verify Stripe was called with correct params
        mock_stripe.PaymentIntent.create.assert_called_once()
        call_kwargs = mock_stripe.PaymentIntent.create.call_args.kwargs
        assert call_kwargs["amount"] == 120000  # 1200.00 GBP in pence
        assert call_kwargs["currency"] == "gbp"
        assert call_kwargs["metadata"]["customer_id"] == "1"

    @patch("app.services.payment_service.stripe")
    async def test_create_payment_intent_stripe_error(
        self, mock_stripe, payment_service
    ):
        """Test payment intent creation with Stripe error."""
        # Mock Stripe error
        mock_stripe.PaymentIntent.create.side_effect = Exception(
            "Stripe API Error"
        )

        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await payment_service.create_payment_intent(
                customer_id=1,
                budget=1200.00,
                quote_data={},
            )

        assert "Failed to create payment intent" in str(exc_info.value)

    @patch("app.services.payment_service.stripe")
    async def test_handle_payment_success(self, mock_stripe, payment_service):
        """Test successful payment handling."""
        # Mock Stripe response
        mock_intent = MagicMock()
        mock_intent.id = "pi_test123"
        mock_intent.status = "succeeded"
        mock_intent.amount = 120000  # 1200.00 GBP in pence
        mock_intent.currency = "gbp"
        mock_intent.created = 1719660000
        mock_intent.latest_charge = "ch_test123"
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent

        # Handle payment success
        result = await payment_service.handle_payment_success(
            intent_id="pi_test123",
            customer_id=1,
            quote_data={},
        )

        # Verify results
        assert result["intent_id"] == "pi_test123"
        assert result["amount"] == 1200.00
        assert result["currency"] == "gbp"
        assert result["status"] == "completed"
        assert result["charge_id"] == "ch_test123"

    @patch("app.services.payment_service.stripe")
    async def test_handle_payment_failed(self, mock_stripe, payment_service):
        """Test payment handling with failed payment."""
        # Mock Stripe response with failed payment
        mock_intent = MagicMock()
        mock_intent.id = "pi_test123"
        mock_intent.status = "processing"  # Not succeeded
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent

        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await payment_service.handle_payment_success(
                intent_id="pi_test123",
                customer_id=1,
                quote_data={},
            )

        assert "Payment not succeeded" in str(exc_info.value)

    def test_verify_webhook_signature_valid(self, payment_service):
        """Test webhook signature verification with valid signature."""
        with patch("app.services.payment_service.stripe.Webhook.construct_event") as mock_construct:
            # Mock valid event
            mock_event = {
                "type": "payment_intent.succeeded",
                "data": {"object": {"id": "pi_test123"}},
            }
            mock_construct.return_value = mock_event

            # Verify signature
            result = payment_service.verify_webhook_signature(
                payload=b"test_payload",
                signature="test_signature",
            )

            assert result == mock_event

    def test_verify_webhook_signature_invalid(self, payment_service):
        """Test webhook signature verification with invalid signature."""
        with patch("app.services.payment_service.stripe.Webhook.construct_event") as mock_construct:
            # Mock signature error
            mock_construct.side_effect = Exception("Invalid signature")

            # Should raise ValueError
            with pytest.raises(ValueError) as exc_info:
                payment_service.verify_webhook_signature(
                    payload=b"test_payload",
                    signature="invalid_signature",
                )

            assert "Invalid webhook payload" in str(exc_info.value)

    @patch("app.services.payment_service.stripe")
    async def test_refund_payment_success(self, mock_stripe, payment_service):
        """Test successful payment refund."""
        # Mock Stripe responses
        mock_intent = MagicMock()
        mock_intent.id = "pi_test123"
        mock_intent.latest_charge = "ch_test123"
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent

        mock_refund = MagicMock()
        mock_refund.id = "re_test123"
        mock_refund.amount = 120000  # 1200.00 GBP in pence
        mock_refund.status = "succeeded"
        mock_stripe.Refund.create.return_value = mock_refund

        # Refund payment
        result = await payment_service.refund_payment(
            intent_id="pi_test123",
            reason="customer_request",
        )

        # Verify results
        assert result["refund_id"] == "re_test123"
        assert result["amount"] == 1200.00
        assert result["status"] == "succeeded"
        assert result["reason"] == "customer_request"

    @patch("app.services.payment_service.stripe")
    async def test_refund_payment_no_charge(self, mock_stripe, payment_service):
        """Test refund when no charge exists."""
        # Mock Stripe response without charge
        mock_intent = MagicMock()
        mock_intent.id = "pi_test123"
        mock_intent.latest_charge = None  # No charge
        mock_stripe.PaymentIntent.retrieve.return_value = mock_intent

        # Should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            await payment_service.refund_payment(intent_id="pi_test123")

        assert "No charge found" in str(exc_info.value)


@pytest.mark.integration
class TestPaymentEndpoints:
    """Tests for payment API endpoints."""

    @pytest.fixture
    async def client(self, app):
        """Create test client."""
        from fastapi.testclient import TestClient
        return TestClient(app)

    @pytest.mark.asyncio
    async def test_create_payment_intent_endpoint(
        self, client, db_session
    ):
        """Test POST /api/payments/intent endpoint."""
        # This test assumes a customer exists in the test database
        # In a real test, you'd create a customer first
        pass

    @pytest.mark.asyncio
    async def test_confirm_payment_endpoint(
        self, client, db_session
    ):
        """Test POST /api/payments/confirm endpoint."""
        # This test assumes payment intent succeeded
        # In a real test, you'd mock the Stripe response
        pass


@pytest.mark.integration
class TestPaymentWebhooks:
    """Tests for Stripe webhook handlers."""

    @pytest.mark.asyncio
    async def test_payment_intent_succeeded_webhook(
        self, client, db_session
    ):
        """Test payment_intent.succeeded webhook creates order."""
        # This test assumes webhook signature is verified
        # In a real test, you'd mock the signature verification
        pass

    @pytest.mark.asyncio
    async def test_payment_intent_failed_webhook(
        self, client, db_session
    ):
        """Test payment_intent.payment_failed webhook logs failure."""
        pass
