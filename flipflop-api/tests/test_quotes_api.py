"""Tests for quote generation API endpoints."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.quote import QuoteResponse, BudgetTiersResponse


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestQuoteEndpoints:
    """Test suite for quote API endpoints."""

    def test_get_budget_tiers(self, client):
        """Test GET /api/quotes/budgets endpoint."""
        response = client.get("/api/quotes/budgets")

        assert response.status_code == 200
        data = response.json()

        assert "tiers" in data
        assert "min_budget" in data
        assert "max_budget" in data
        assert len(data["tiers"]) == 5
        assert data["min_budget"] == 800
        assert data["max_budget"] == 3000

    def test_get_budget_tiers_structure(self, client):
        """Test budget tiers response structure."""
        response = client.get("/api/quotes/budgets")

        assert response.status_code == 200
        data = response.json()

        # Check first tier
        first_tier = data["tiers"][0]
        assert first_tier["budget"] == 800
        assert "name" in first_tier
        assert "specs" in first_tier
        assert isinstance(first_tier["specs"], dict)
        assert "cpu" in first_tier["specs"]
        assert "gpu" in first_tier["specs"]

    def test_get_budget_tiers_all_tiers(self, client):
        """Test that all budget tiers are returned."""
        response = client.get("/api/quotes/budgets")

        assert response.status_code == 200
        data = response.json()

        budgets = [tier["budget"] for tier in data["tiers"]]
        assert budgets == [800, 1200, 1500, 2000, 3000]

    @patch("app.routes.quotes.QuoteService.generate_quote")
    def test_generate_quote_valid_budget(self, mock_generate, client):
        """Test POST /api/quotes/generate with valid budget."""
        # Mock the service to return a quote
        mock_quote = {
            "budget": 1200,
            "tier_name": "Mid-Range Gaming",
            "recommended_specs": {
                "cpu": "Ryzen 5 5600X",
                "gpu": "RTX 3070",
                "ram": "16GB DDR5",
                "ssd": "1TB NVMe",
                "motherboard": "B850",
                "psu": "750W Gold",
                "cooler": "Noctua NH-D15",
                "case": "Mid Tower",
            },
            "components": [
                {
                    "component_type": "cpu",
                    "component_category": "CPU",
                    "component_name": "Ryzen 5 5600X",
                    "price": 250.0,
                    "quantity": 1,
                },
                {
                    "component_type": "gpu",
                    "component_category": "GPU",
                    "component_name": "RTX 3070",
                    "price": 400.0,
                    "quantity": 1,
                },
            ],
            "parts_cost_total": 2000.0,
            "labor_cost": 87.5,
            "overhead_cost": 208.75,
            "subtotal": 2087.5,
            "total_price": 2296.25,
            "estimated_build_days": 7,
            "budget_remaining": -1096.25,
            "within_budget": False,
        }
        mock_generate.return_value = mock_quote

        response = client.post("/api/quotes/generate", json={"budget": 1200})

        assert response.status_code == 200
        data = response.json()

        assert data["budget"] == 1200
        assert data["tier_name"] == "Mid-Range Gaming"
        assert data["total_price"] == 2296.25
        assert "components" in data

    @patch("app.routes.quotes.QuoteService.generate_quote")
    def test_generate_quote_returns_within_budget_flag(self, mock_generate, client):
        """Test that quote response includes within_budget flag."""
        mock_quote = {
            "budget": 800,
            "tier_name": "Budget Gaming",
            "recommended_specs": {},
            "components": [],
            "parts_cost_total": 400.0,
            "labor_cost": 87.5,
            "overhead_cost": 48.75,
            "subtotal": 487.5,
            "total_price": 536.25,
            "estimated_build_days": 7,
            "budget_remaining": 263.75,
            "within_budget": True,
        }
        mock_generate.return_value = mock_quote

        response = client.post("/api/quotes/generate", json={"budget": 800})

        assert response.status_code == 200
        data = response.json()

        assert data["within_budget"] is True
        assert data["budget_remaining"] == 263.75

    def test_generate_quote_budget_below_minimum(self, client):
        """Test POST /api/quotes/generate with budget below minimum."""
        response = client.post("/api/quotes/generate", json={"budget": 500})

        assert response.status_code == 400
        assert "Budget must be between" in response.json()["detail"]

    def test_generate_quote_budget_above_maximum(self, client):
        """Test POST /api/quotes/generate with budget above maximum."""
        response = client.post("/api/quotes/generate", json={"budget": 5000})

        assert response.status_code == 400
        assert "Budget must be between" in response.json()["detail"]

    @patch("app.routes.quotes.QuoteService.generate_quote")
    def test_generate_quote_service_returns_none(self, mock_generate, client):
        """Test POST /api/quotes/generate when service returns None."""
        mock_generate.return_value = None

        response = client.post("/api/quotes/generate", json={"budget": 1200})

        assert response.status_code == 400
        assert "Unable to generate quote" in response.json()["detail"]

    def test_generate_quote_invalid_request(self, client):
        """Test POST /api/quotes/generate with invalid request."""
        response = client.post("/api/quotes/generate", json={"budget": "invalid"})

        assert response.status_code == 422  # Validation error

    def test_generate_quote_missing_budget(self, client):
        """Test POST /api/quotes/generate with missing budget field."""
        response = client.post("/api/quotes/generate", json={})

        assert response.status_code == 422  # Validation error

    @patch("app.routes.quotes.QuoteService.generate_quote")
    def test_generate_quote_minimum_budget(self, mock_generate, client):
        """Test generate quote at minimum budget."""
        mock_quote = {
            "budget": 800,
            "tier_name": "Budget Gaming",
            "recommended_specs": {},
            "components": [],
            "parts_cost_total": 500.0,
            "labor_cost": 87.5,
            "overhead_cost": 58.75,
            "subtotal": 587.5,
            "total_price": 646.25,
            "estimated_build_days": 7,
            "budget_remaining": 153.75,
            "within_budget": True,
        }
        mock_generate.return_value = mock_quote

        response = client.post("/api/quotes/generate", json={"budget": 800})

        assert response.status_code == 200

    @patch("app.routes.quotes.QuoteService.generate_quote")
    def test_generate_quote_maximum_budget(self, mock_generate, client):
        """Test generate quote at maximum budget."""
        mock_quote = {
            "budget": 3000,
            "tier_name": "High-End Workstation",
            "recommended_specs": {},
            "components": [],
            "parts_cost_total": 2500.0,
            "labor_cost": 87.5,
            "overhead_cost": 258.75,
            "subtotal": 2587.5,
            "total_price": 2846.25,
            "estimated_build_days": 7,
            "budget_remaining": 153.75,
            "within_budget": True,
        }
        mock_generate.return_value = mock_quote

        response = client.post("/api/quotes/generate", json={"budget": 3000})

        assert response.status_code == 200

    @patch("app.routes.quotes.QuoteService.generate_quote")
    def test_generate_quote_response_schema_validation(self, mock_generate, client):
        """Test that response validates against schema."""
        mock_quote = {
            "budget": 1200,
            "tier_name": "Mid-Range Gaming",
            "recommended_specs": {"cpu": "Ryzen 5 5600X"},
            "components": [
                {
                    "component_type": "cpu",
                    "component_category": "CPU",
                    "component_name": "Ryzen 5 5600X",
                    "price": 250.0,
                    "quantity": 1,
                }
            ],
            "parts_cost_total": 250.0,
            "labor_cost": 87.5,
            "overhead_cost": 33.75,
            "subtotal": 337.5,
            "total_price": 371.25,
            "estimated_build_days": 7,
            "budget_remaining": 828.75,
            "within_budget": True,
        }
        mock_generate.return_value = mock_quote

        response = client.post("/api/quotes/generate", json={"budget": 1200})

        assert response.status_code == 200
        # Verify response can be parsed as QuoteResponse
        quote_response = QuoteResponse(**response.json())
        assert quote_response.budget == 1200

    def test_get_budget_tiers_response_schema(self, client):
        """Test that budget tiers response validates against schema."""
        response = client.get("/api/quotes/budgets")

        assert response.status_code == 200
        # Verify response can be parsed as BudgetTiersResponse
        tiers_response = BudgetTiersResponse(**response.json())
        assert len(tiers_response.tiers) == 5
