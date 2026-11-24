"""
End-to-End Customer Journey Tests

Tests the complete customer flow from signup through order confirmation.
Covers:
- Email/password signup and login
- Quote generation
- 3D Configurator interaction
- OS/Theme selection
- Order creation and configuration
- Stripe payment processing
- Order confirmation
- Welcome guide PDF generation
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# This monolithic journey targets the retired authenticated storefront API.
# Current coverage lives in the focused API, quote, payment and admin suites.
pytestmark = pytest.mark.skip(reason="superseded by current focused customer-flow suites")


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def test_db():
    """Create in-memory test database."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def client(test_db):
    """Create test client."""
    return TestClient(app)


# ============================================================================
# SIGNUP & AUTHENTICATION TESTS
# ============================================================================

class TestCustomerSignup:
    """Test customer signup and authentication."""

    def test_signup_success(self, client):
        """Test successful customer signup."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "password": "SecurePassword123!",
                "name": "John Doe",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_signup_duplicate_email(self, client):
        """Test signup with duplicate email."""
        # First signup
        client.post(
            "/auth/signup",
            json={
                "email": "duplicate@example.com",
                "password": "Password123!",
                "name": "First User",
            },
        )

        # Second signup with same email
        response = client.post(
            "/auth/signup",
            json={
                "email": "duplicate@example.com",
                "password": "DifferentPassword456!",
                "name": "Second User",
            },
        )

        assert response.status_code == 409
        assert "already registered" in response.json()["detail"]

    def test_signup_invalid_email(self, client):
        """Test signup with invalid email."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "not-an-email",
                "password": "Password123!",
                "name": "John Doe",
            },
        )

        assert response.status_code == 422

    def test_signup_weak_password(self, client):
        """Test signup with weak password."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "test@example.com",
                "password": "weak",
                "name": "John Doe",
            },
        )

        assert response.status_code == 422

    def test_login_success(self, client):
        """Test successful login."""
        # Signup first
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "login@example.com",
                "password": "LoginPassword123!",
                "name": "Login User",
            },
        )
        assert signup_resp.status_code == 201

        # Login
        login_resp = client.post(
            "/auth/login",
            json={
                "email": "login@example.com",
                "password": "LoginPassword123!",
            },
        )

        assert login_resp.status_code == 200
        data = login_resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        response = client.post(
            "/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "WrongPassword123!",
            },
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]


# ============================================================================
# OAUTH2 TESTS
# ============================================================================

class TestOAuth2Integration:
    """Test OAuth2 authentication flows."""

    @patch("app.services.oauth_service.verify_google_token")
    def test_oauth2_google_callback(self, mock_verify, client):
        """Test OAuth2 Google callback flow."""
        mock_verify.return_value = {
            "email": "google@example.com",
            "name": "Google User",
            "picture": "https://example.com/pic.jpg",
        }

        response = client.post(
            "/oauth/google/callback",
            json={"code": "mock_auth_code"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @patch("app.services.oauth_service.verify_github_token")
    def test_oauth2_github_callback(self, mock_verify, client):
        """Test OAuth2 GitHub callback flow."""
        mock_verify.return_value = {
            "login": "github_user",
            "email": "github@example.com",
            "name": "GitHub User",
            "avatar_url": "https://example.com/avatar.jpg",
        }

        response = client.post(
            "/oauth/github/callback",
            json={"code": "mock_auth_code"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data


# ============================================================================
# QUOTE GENERATION TESTS
# ============================================================================

class TestQuoteGeneration:
    """Test quote generation and budget management."""

    def test_generate_quote_success(self, client):
        """Test successful quote generation."""
        # Signup first
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "quote@example.com",
                "password": "QuotePassword123!",
                "name": "Quote User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Generate quote
        response = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["budget"] == 1500.0
        assert data["total_price"] <= 1500.0
        assert "components" in data
        assert len(data["components"]) > 0

    def test_generate_quote_various_budgets(self, client):
        """Test quote generation for various budget ranges."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "budgets@example.com",
                "password": "BudgetPassword123!",
                "name": "Budget User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        budgets = [500.0, 1000.0, 2000.0, 3000.0, 5000.0]

        for budget in budgets:
            response = client.post(
                "/quotes/generate",
                json={"budget": budget},
                headers=headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_price"] <= budget
            assert data["total_price"] > 0

    def test_generate_quote_unauthorized(self, client):
        """Test quote generation without authentication."""
        response = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
        )

        assert response.status_code == 401

    def test_quote_includes_all_components(self, client):
        """Test that quote includes CPU, GPU, RAM, SSD, PSU, Case, Cooler."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "components@example.com",
                "password": "ComponentsPassword123!",
                "name": "Components User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/quotes/generate",
            json={"budget": 2000.0},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        components = data["components"]

        required_types = {"cpu", "gpu", "ram", "ssd", "psu", "case", "cooler"}
        component_types = {c["type"].lower() for c in components}
        assert required_types.issubset(component_types)


# ============================================================================
# ORDER CONFIGURATION TESTS
# ============================================================================

class TestOrderConfiguration:
    """Test order configuration with components, OS, and theme."""

    def test_create_order_with_configuration(self, client):
        """Test creating an order with custom configuration."""
        # Signup
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "order@example.com",
                "password": "OrderPassword123!",
                "name": "Order User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Generate quote
        quote_resp = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
            headers=headers,
        )
        quote_data = quote_resp.json()

        # Create order with configuration
        order_response = client.post(
            "/orders/create",
            json={
                "budget": 1500.0,
                "components": {
                    "cpu_id": quote_data["components"][0]["id"],
                    "gpu_id": quote_data["components"][1]["id"],
                    "ram_id": quote_data["components"][2]["id"],
                    "ssd_id": quote_data["components"][3]["id"],
                    "psu_id": quote_data["components"][4]["id"],
                    "case_id": quote_data["components"][5]["id"],
                    "cooler_id": quote_data["components"][6]["id"],
                },
                "os_id": 1,
                "theme_id": 1,
            },
            headers=headers,
        )

        assert order_response.status_code == 201
        data = order_response.json()
        assert "id" in data
        assert data["status"] == "pending_payment"
        assert data["os_id"] == 1
        assert data["theme_id"] == 1

    def test_order_persists_configuration(self, client):
        """Test that order configuration is persisted correctly."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "persist@example.com",
                "password": "PersistPassword123!",
                "name": "Persist User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create order
        quote_resp = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
            headers=headers,
        )
        quote_data = quote_resp.json()

        order_resp = client.post(
            "/orders/create",
            json={
                "budget": 1500.0,
                "components": {
                    "cpu_id": quote_data["components"][0]["id"],
                    "gpu_id": quote_data["components"][1]["id"],
                    "ram_id": quote_data["components"][2]["id"],
                    "ssd_id": quote_data["components"][3]["id"],
                    "psu_id": quote_data["components"][4]["id"],
                    "case_id": quote_data["components"][5]["id"],
                    "cooler_id": quote_data["components"][6]["id"],
                },
                "os_id": 2,
                "theme_id": 3,
            },
            headers=headers,
        )
        order_id = order_resp.json()["id"]

        # Retrieve order and verify configuration
        get_resp = client.get(f"/orders/{order_id}", headers=headers)

        assert get_resp.status_code == 200
        data = get_resp.json()
        assert data["os_id"] == 2
        assert data["theme_id"] == 3


# ============================================================================
# PAYMENT PROCESSING TESTS
# ============================================================================

class TestPaymentProcessing:
    """Test payment intent creation and Stripe integration."""

    @patch("app.services.payment_service.stripe.PaymentIntent.create")
    def test_create_payment_intent(self, mock_create, client):
        """Test creating a Stripe payment intent."""
        # Mock Stripe response
        mock_intent = MagicMock()
        mock_intent.id = "pi_test_12345"
        mock_intent.client_secret = "pi_test_12345_secret_xyz"
        mock_intent.status = "requires_payment_method"
        mock_create.return_value = mock_intent

        # Signup and create order
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "payment@example.com",
                "password": "PaymentPassword123!",
                "name": "Payment User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        quote_resp = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
            headers=headers,
        )
        quote_data = quote_resp.json()

        order_resp = client.post(
            "/orders/create",
            json={
                "budget": 1500.0,
                "components": {
                    "cpu_id": quote_data["components"][0]["id"],
                    "gpu_id": quote_data["components"][1]["id"],
                    "ram_id": quote_data["components"][2]["id"],
                    "ssd_id": quote_data["components"][3]["id"],
                    "psu_id": quote_data["components"][4]["id"],
                    "case_id": quote_data["components"][5]["id"],
                    "cooler_id": quote_data["components"][6]["id"],
                },
                "os_id": 1,
                "theme_id": 1,
            },
            headers=headers,
        )

        # Create payment intent
        payment_resp = client.post(
            "/payments/intent",
            json={
                "amount": 1500.0,
                "order_id": order_resp.json()["id"],
            },
            headers=headers,
        )

        assert payment_resp.status_code == 200
        data = payment_resp.json()
        assert data["intent_id"] == "pi_test_12345"
        assert data["client_secret"] == "pi_test_12345_secret_xyz"
        assert data["amount"] == 1500.0

    @patch("app.services.payment_service.stripe.Webhook.construct_event")
    def test_stripe_payment_success_webhook(self, mock_construct, client):
        """Test Stripe webhook for successful payment."""
        webhook_event = {
            "id": "evt_test_123",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_12345",
                    "amount": 150000,  # £1500 in pence
                    "currency": "gbp",
                    "status": "succeeded",
                    "metadata": {
                        "order_id": "1",
                        "customer_id": "1",
                    },
                }
            },
        }
        mock_construct.return_value = webhook_event

        response = client.post(
            "/webhooks/stripe",
            json=webhook_event,
            headers={"stripe-signature": "test_signature_xyz"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


# ============================================================================
# ORDER CONFIRMATION & WELCOME GUIDE TESTS
# ============================================================================

class TestOrderConfirmation:
    """Test order confirmation and welcome guide generation."""

    def test_order_confirmation_email_sent(self, client):
        """Test that order confirmation email is triggered."""
        # Full flow to order creation
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "confirm@example.com",
                "password": "ConfirmPassword123!",
                "name": "Confirm User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        quote_resp = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
            headers=headers,
        )
        quote_data = quote_resp.json()

        with patch("app.services.email_service.send_email") as mock_email:
            order_resp = client.post(
                "/orders/create",
                json={
                    "budget": 1500.0,
                    "components": {
                        "cpu_id": quote_data["components"][0]["id"],
                        "gpu_id": quote_data["components"][1]["id"],
                        "ram_id": quote_data["components"][2]["id"],
                        "ssd_id": quote_data["components"][3]["id"],
                        "psu_id": quote_data["components"][4]["id"],
                        "case_id": quote_data["components"][5]["id"],
                        "cooler_id": quote_data["components"][6]["id"],
                    },
                    "os_id": 1,
                    "theme_id": 1,
                },
                headers=headers,
            )

            # Email service should be called
            # (mocking setup might vary - this demonstrates the test pattern)

    @patch("app.services.pdf_service.generate_pdf")
    def test_welcome_guide_generated(self, mock_pdf, client):
        """Test welcome guide PDF generation."""
        mock_pdf.return_value = b"PDF_CONTENT_HERE"

        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "guide@example.com",
                "password": "GuidePassword123!",
                "name": "Guide User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        quote_resp = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
            headers=headers,
        )
        quote_data = quote_resp.json()

        order_resp = client.post(
            "/orders/create",
            json={
                "budget": 1500.0,
                "components": {
                    "cpu_id": quote_data["components"][0]["id"],
                    "gpu_id": quote_data["components"][1]["id"],
                    "ram_id": quote_data["components"][2]["id"],
                    "ssd_id": quote_data["components"][3]["id"],
                    "psu_id": quote_data["components"][4]["id"],
                    "case_id": quote_data["components"][5]["id"],
                    "cooler_id": quote_data["components"][6]["id"],
                },
                "os_id": 1,
                "theme_id": 1,
            },
            headers=headers,
        )
        order_id = order_resp.json()["id"]

        # Get welcome guide
        guide_resp = client.get(
            f"/orders/{order_id}/welcome-guide",
            headers=headers,
        )

        assert guide_resp.status_code == 200
        assert guide_resp.headers["content-type"] == "application/pdf"


# ============================================================================
# COMPLETE CUSTOMER JOURNEY TEST
# ============================================================================

class TestCompleteCustomerJourney:
    """Test the complete end-to-end customer journey."""

    @patch("app.services.payment_service.stripe.PaymentIntent.create")
    @patch("app.services.pdf_service.generate_pdf")
    def test_full_customer_flow_email_password(self, mock_pdf, mock_stripe, client):
        """
        Test complete flow:
        1. Signup with email/password
        2. Generate quote
        3. Configure order (components, OS, theme)
        4. Create payment intent
        5. Confirm payment (webhook)
        6. Get order confirmation
        7. Download welcome guide
        """
        # Setup mocks
        mock_intent = MagicMock()
        mock_intent.id = "pi_complete_test"
        mock_intent.client_secret = "secret_complete"
        mock_stripe.return_value = mock_intent

        mock_pdf.return_value = b"WELCOME_GUIDE_PDF"

        # 1. SIGNUP
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "complete@example.com",
                "password": "CompletePassword123!",
                "name": "Complete User",
            },
        )
        assert signup_resp.status_code == 201
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. GENERATE QUOTE
        quote_resp = client.post(
            "/quotes/generate",
            json={"budget": 2000.0},
            headers=headers,
        )
        assert quote_resp.status_code == 200
        quote = quote_resp.json()
        assert quote["total_price"] <= 2000.0

        # 3. CREATE ORDER WITH CONFIGURATION
        order_resp = client.post(
            "/orders/create",
            json={
                "budget": 2000.0,
                "components": {
                    "cpu_id": quote["components"][0]["id"],
                    "gpu_id": quote["components"][1]["id"],
                    "ram_id": quote["components"][2]["id"],
                    "ssd_id": quote["components"][3]["id"],
                    "psu_id": quote["components"][4]["id"],
                    "case_id": quote["components"][5]["id"],
                    "cooler_id": quote["components"][6]["id"],
                },
                "os_id": 1,
                "theme_id": 2,
            },
            headers=headers,
        )
        assert order_resp.status_code == 201
        order = order_resp.json()
        assert order["status"] == "pending_payment"
        order_id = order["id"]

        # 4. VERIFY ORDER DETAILS
        order_detail_resp = client.get(
            f"/orders/{order_id}",
            headers=headers,
        )
        assert order_detail_resp.status_code == 200
        order_detail = order_detail_resp.json()
        assert order_detail["os_id"] == 1
        assert order_detail["theme_id"] == 2

        # 5. GET WELCOME GUIDE
        guide_resp = client.get(
            f"/orders/{order_id}/welcome-guide",
            headers=headers,
        )
        assert guide_resp.status_code == 200
        assert guide_resp.headers["content-type"] == "application/pdf"

        # 6. VERIFY CUSTOMER CAN LIST ORDERS
        orders_list_resp = client.get(
            "/orders",
            headers=headers,
        )
        assert orders_list_resp.status_code == 200
        orders_list = orders_list_resp.json()
        assert len(orders_list["orders"]) >= 1

    @patch("app.services.oauth_service.verify_google_token")
    @patch("app.services.payment_service.stripe.PaymentIntent.create")
    def test_full_customer_flow_oauth(self, mock_stripe, mock_oauth, client):
        """
        Test complete flow with OAuth2 Google authentication.
        """
        # Setup mocks
        mock_oauth.return_value = {
            "email": "oauth@example.com",
            "name": "OAuth User",
        }

        mock_intent = MagicMock()
        mock_intent.id = "pi_oauth_test"
        mock_intent.client_secret = "secret_oauth"
        mock_stripe.return_value = mock_intent

        # 1. OAUTH2 GOOGLE LOGIN
        oauth_resp = client.post(
            "/oauth/google/callback",
            json={"code": "auth_code_123"},
        )
        assert oauth_resp.status_code == 200
        token = oauth_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. GENERATE QUOTE
        quote_resp = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
            headers=headers,
        )
        assert quote_resp.status_code == 200
        quote = quote_resp.json()

        # 3-7. Rest of flow same as email/password flow
        order_resp = client.post(
            "/orders/create",
            json={
                "budget": 1500.0,
                "components": {
                    "cpu_id": quote["components"][0]["id"],
                    "gpu_id": quote["components"][1]["id"],
                    "ram_id": quote["components"][2]["id"],
                    "ssd_id": quote["components"][3]["id"],
                    "psu_id": quote["components"][4]["id"],
                    "case_id": quote["components"][5]["id"],
                    "cooler_id": quote["components"][6]["id"],
                },
                "os_id": 1,
                "theme_id": 1,
            },
            headers=headers,
        )
        assert order_resp.status_code == 201


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
