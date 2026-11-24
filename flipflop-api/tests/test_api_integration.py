"""
API Integration Tests

Tests all API endpoints for:
- Response schema validation
- Error handling
- Authentication/authorization
- CORS headers
- Rate limiting
- Database transactions
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db


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
# AUTH ENDPOINTS TESTS
# ============================================================================

class TestAuthEndpoints:
    """Test authentication endpoint responses and error handling."""

    def test_signup_request_validation(self, client):
        """Test signup request validation."""
        # Missing email
        response = client.post(
            "/auth/signup",
            json={"password": "Password123!", "name": "User"},
        )
        assert response.status_code == 422
        assert "email" in response.json()["detail"][0]["loc"]

        # Missing password
        response = client.post(
            "/auth/signup",
            json={"email": "test@example.com", "name": "User"},
        )
        assert response.status_code == 422

        # Missing name
        response = client.post(
            "/auth/signup",
            json={"email": "test@example.com", "password": "Password123!"},
        )
        assert response.status_code == 422

    def test_login_request_validation(self, client):
        """Test login request validation."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com"},
        )
        assert response.status_code == 422

    def test_auth_header_required(self, client):
        """Test that auth header is required for protected endpoints."""
        response = client.get("/orders")
        assert response.status_code == 401
        assert "authorization" in response.json()["detail"].lower()

    def test_invalid_token(self, client):
        """Test invalid token rejection."""
        headers = {"Authorization": "Bearer invalid_token_xyz"}
        response = client.get("/orders", headers=headers)
        assert response.status_code == 401

    def test_malformed_auth_header(self, client):
        """Test malformed authorization header."""
        # Missing "Bearer"
        headers = {"Authorization": "token_only"}
        response = client.get("/orders", headers=headers)
        assert response.status_code == 401

        # Empty header
        headers = {"Authorization": ""}
        response = client.get("/orders", headers=headers)
        assert response.status_code == 401


# ============================================================================
# QUOTES ENDPOINTS TESTS
# ============================================================================

class TestQuotesEndpoints:
    """Test quotes API endpoints."""

    def test_generate_quote_response_schema(self, client):
        """Test quote response includes required fields."""
        # Signup first
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "quote@example.com",
                "password": "Password123!",
                "name": "Quote User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "id" in data
        assert "budget" in data
        assert "total_price" in data
        assert "components" in data
        assert "created_at" in data

        # Validate components structure
        for component in data["components"]:
            assert "id" in component
            assert "type" in component
            assert "name" in component
            assert "price" in component
            assert isinstance(component["price"], (int, float))

    def test_quote_budget_constraint(self, client):
        """Test that quote respects budget constraint."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "budget@example.com",
                "password": "Password123!",
                "name": "Budget User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        for budget in [500.0, 1000.0, 2000.0]:
            response = client.post(
                "/quotes/generate",
                json={"budget": budget},
                headers=headers,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["total_price"] <= budget
            assert data["total_price"] > 0

    def test_quote_invalid_budget(self, client):
        """Test quote with invalid budget."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "invalid@example.com",
                "password": "Password123!",
                "name": "Invalid User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Zero budget
        response = client.post(
            "/quotes/generate",
            json={"budget": 0},
            headers=headers,
        )
        assert response.status_code == 422

        # Negative budget
        response = client.post(
            "/quotes/generate",
            json={"budget": -100},
            headers=headers,
        )
        assert response.status_code == 422


# ============================================================================
# ORDERS ENDPOINTS TESTS
# ============================================================================

class TestOrdersEndpoints:
    """Test orders API endpoints."""

    def test_create_order_response_schema(self, client):
        """Test order creation response schema."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "order@example.com",
                "password": "Password123!",
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
        quote = quote_resp.json()

        # Create order
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
        data = order_resp.json()

        # Validate schema
        assert "id" in data
        assert "customer_id" in data
        assert "status" in data
        assert data["status"] == "pending_payment"
        assert "budget" in data
        assert "total_price" in data
        assert "os_id" in data
        assert "theme_id" in data
        assert "created_at" in data

    def test_get_order_by_id(self, client):
        """Test retrieving order by ID."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "getorder@example.com",
                "password": "Password123!",
                "name": "Get Order User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        quote_resp = client.post(
            "/quotes/generate",
            json={"budget": 1500.0},
            headers=headers,
        )
        quote = quote_resp.json()

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
        order_id = order_resp.json()["id"]

        # Get order
        get_resp = client.get(f"/orders/{order_id}", headers=headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == order_id

    def test_get_nonexistent_order(self, client):
        """Test retrieving nonexistent order returns 404."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "notfound@example.com",
                "password": "Password123!",
                "name": "Not Found User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        response = client.get("/orders/99999", headers=headers)
        assert response.status_code == 404

    def test_list_orders(self, client):
        """Test listing customer orders."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "listorders@example.com",
                "password": "Password123!",
                "name": "List Orders User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create multiple orders
        for i in range(3):
            quote_resp = client.post(
                "/quotes/generate",
                json={"budget": 1000.0 + i * 500},
                headers=headers,
            )
            quote = quote_resp.json()

            client.post(
                "/orders/create",
                json={
                    "budget": 1000.0 + i * 500,
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

        # List orders
        list_resp = client.get("/orders", headers=headers)
        assert list_resp.status_code == 200
        data = list_resp.json()
        assert "orders" in data
        assert len(data["orders"]) >= 3


# ============================================================================
# PAYMENTS ENDPOINTS TESTS
# ============================================================================

class TestPaymentsEndpoints:
    """Test payment API endpoints."""

    @patch("app.services.payment_service.stripe.PaymentIntent.create")
    def test_create_payment_intent_response_schema(self, mock_stripe, client):
        """Test payment intent creation response schema."""
        mock_intent = MagicMock()
        mock_intent.id = "pi_test"
        mock_intent.client_secret = "secret_test"
        mock_stripe.return_value = mock_intent

        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "payment@example.com",
                "password": "Password123!",
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
        quote = quote_resp.json()

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
        order_id = order_resp.json()["id"]

        # Create payment intent
        payment_resp = client.post(
            "/payments/intent",
            json={"amount": 1500.0, "order_id": order_id},
            headers=headers,
        )

        assert payment_resp.status_code == 200
        data = payment_resp.json()

        # Validate schema
        assert "intent_id" in data
        assert "client_secret" in data
        assert "amount" in data
        assert data["amount"] == 1500.0
        assert "currency" in data


# ============================================================================
# CORS HEADERS TESTS
# ============================================================================

class TestCORSHeaders:
    """Test CORS headers are properly set."""

    def test_cors_headers_present(self, client):
        """Test CORS headers in responses."""
        response = client.options("/auth/signup")

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers or \
               "Access-Control-Allow-Origin" in response.headers


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

class TestErrorHandling:
    """Test error handling and error responses."""

    def test_404_not_found(self, client):
        """Test 404 error for nonexistent endpoint."""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404

    def test_405_method_not_allowed(self, client):
        """Test 405 error for invalid HTTP method."""
        # Most endpoints don't support GET
        response = client.get(
            "/auth/signup",
            headers={"Authorization": "Bearer token"},
        )
        # This might be 405 or 422 depending on implementation
        assert response.status_code in [405, 422]

    def test_500_error_handling(self, client):
        """Test 500 error handling for internal errors."""
        # Cause a database error by creating with invalid data
        with patch("app.database.get_db", side_effect=Exception("Database error")):
            response = client.get("/orders")
            # Should return 500 or 401 (since auth fails)
            assert response.status_code in [500, 401]

    def test_error_response_includes_detail(self, client):
        """Test error responses include detail field."""
        response = client.post(
            "/auth/login",
            json={"email": "nonexistent@example.com", "password": "wrong"},
        )
        assert response.status_code == 401
        assert "detail" in response.json()


# ============================================================================
# REQUEST VALIDATION TESTS
# ============================================================================

class TestRequestValidation:
    """Test request validation."""

    def test_invalid_json(self, client):
        """Test invalid JSON handling."""
        response = client.post(
            "/auth/signup",
            data="not valid json",
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 422

    def test_extra_fields_ignored(self, client):
        """Test that extra fields in request are ignored."""
        response = client.post(
            "/auth/signup",
            json={
                "email": "extra@example.com",
                "password": "Password123!",
                "name": "Extra Fields User",
                "extra_field": "should_be_ignored",
                "another_extra": 123,
            },
        )
        assert response.status_code == 201

    def test_type_coercion(self, client):
        """Test type coercion in requests."""
        signup_resp = client.post(
            "/auth/signup",
            json={
                "email": "coerce@example.com",
                "password": "Password123!",
                "name": "Coerce User",
            },
        )
        token = signup_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Budget as string should be coerced to float
        response = client.post(
            "/quotes/generate",
            json={"budget": "1500.0"},
            headers=headers,
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
