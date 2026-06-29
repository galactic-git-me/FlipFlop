"""
Tests for GemRecommendationService.

Tests cover:
- Demand analysis from order data
- Claude API integration
- Profit margin calculations
- Risk assessment
- Recommendation storage and retrieval
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.gem import GemBuild, GemRiskLevel
from app.models.order import Order, OrderStatus
from app.models.customer import Customer
from app.services.gem_service import GemRecommendationService


@pytest.fixture
async def db_with_orders(db: AsyncSession):
    """Create test database with sample orders."""
    # Create a customer
    customer = Customer(
        name="Test Customer",
        email="test@example.com",
        phone="07700000000",
    )
    db.add(customer)
    await db.flush()

    # Create test orders with different budgets and specs
    orders_data = [
        {
            "order_id": "FF-2026-0001",
            "customer_price": 1200.0,
            "component_costs": 800.0,
            "overhead_amount": 80.0,
            "promised_delivery_date": datetime.utcnow() + timedelta(days=14),
            "status": OrderStatus.COMPLETED,
            "specs": {
                "cpu": "Intel i7-14700K",
                "gpu": "RTX 4070",
                "use_case": "gaming",
                "ram_gb": 32,
                "ssd_gb": 1000,
            }
        },
        {
            "order_id": "FF-2026-0002",
            "customer_price": 1100.0,
            "component_costs": 750.0,
            "overhead_amount": 75.0,
            "promised_delivery_date": datetime.utcnow() + timedelta(days=14),
            "status": OrderStatus.COMPLETED,
            "specs": {
                "cpu": "Intel i7-14700K",
                "gpu": "RTX 4070",
                "use_case": "gaming",
                "ram_gb": 32,
                "ssd_gb": 1000,
            }
        },
        {
            "order_id": "FF-2026-0003",
            "customer_price": 2500.0,
            "component_costs": 1800.0,
            "overhead_amount": 180.0,
            "promised_delivery_date": datetime.utcnow() + timedelta(days=14),
            "status": OrderStatus.READY_TO_SHIP,
            "specs": {
                "cpu": "Intel i9-14900K",
                "gpu": "RTX 4090",
                "use_case": "workstation",
                "ram_gb": 64,
                "ssd_gb": 2000,
            }
        },
        {
            "order_id": "FF-2026-0004",
            "customer_price": 900.0,
            "component_costs": 600.0,
            "overhead_amount": 60.0,
            "promised_delivery_date": datetime.utcnow() + timedelta(days=14),
            "status": OrderStatus.COMPLETED,
            "specs": {
                "cpu": "Intel i5-14600K",
                "gpu": "RTX 4060",
                "use_case": "office",
                "ram_gb": 16,
                "ssd_gb": 512,
            }
        },
    ]

    for order_data in orders_data:
        order = Order(
            customer_id=customer.id,
            **order_data
        )
        db.add(order)

    await db.commit()
    return db, customer


@pytest.mark.asyncio
async def test_analyze_demand(db_with_orders):
    """Test demand analysis from order data."""
    db, _ = db_with_orders
    service = GemRecommendationService(db)

    analysis = await service._analyze_demand(30)

    # Verify analysis structure
    assert "total_orders" in analysis
    assert analysis["total_orders"] == 4
    assert "budget_distribution" in analysis
    assert "use_cases" in analysis
    assert "popular_combos" in analysis
    assert "insights" in analysis

    # Verify budget distribution
    assert len(analysis["budget_distribution"]) > 0
    assert "£1000-1200" in analysis["budget_distribution"]
    assert analysis["budget_distribution"]["£1000-1200"] >= 2

    # Verify use cases
    assert "gaming" in analysis["use_cases"]
    assert analysis["use_cases"]["gaming"] >= 2

    # Verify insights
    insights = analysis["insights"]
    assert insights["avg_budget_gbp"] > 0
    assert insights["median_budget_gbp"] > 0
    assert "most_popular_use_case" in insights


@pytest.mark.asyncio
async def test_get_budget_bucket():
    """Test budget bucketing logic."""
    assert GemRecommendationService._get_budget_bucket(400) == "£0-500"
    assert GemRecommendationService._get_budget_bucket(700) == "£500-800"
    assert GemRecommendationService._get_budget_bucket(950) == "£800-1000"
    assert GemRecommendationService._get_budget_bucket(1150) == "£1000-1200"
    assert GemRecommendationService._get_budget_bucket(2500) == "£2000+"


@pytest.mark.asyncio
async def test_get_market_prices():
    """Test market price fetching."""
    prices = GemRecommendationService._get_market_prices()

    assert "CPUs" in prices
    assert "GPUs" in prices
    assert "RAM" in prices
    assert "Storage" in prices
    assert "PSU" in prices
    assert "Cases" in prices

    # Verify some common components exist
    assert "Intel i9-14900K" in prices["CPUs"]
    assert "RTX 4090" in prices["GPUs"]
    assert prices["CPUs"]["Intel i9-14900K"] > 0
    assert prices["GPUs"]["RTX 4090"] > 0


@pytest.mark.asyncio
async def test_find_component_price():
    """Test component price lookup."""
    prices = {"RTX 4090": 1399, "RTX 4080": 899, "RTX 4070": 499}

    # Exact match
    assert GemRecommendationService._find_component_price("RTX 4090", prices) == 1399

    # Substring match
    assert GemRecommendationService._find_component_price("RTX 4090 OC", prices) == 1399
    assert GemRecommendationService._find_component_price("4080 Gaming", prices) == 899

    # Not found
    assert GemRecommendationService._find_component_price("RTX 4070 Ti", prices) == 499
    assert GemRecommendationService._find_component_price("RTX 3090", prices) == 0.0

    # None input
    assert GemRecommendationService._find_component_price(None, prices) == 0.0
    assert GemRecommendationService._find_component_price("RTX 4090", {}) == 0.0


@pytest.mark.asyncio
async def test_estimate_ram_cost():
    """Test RAM cost estimation."""
    prices = {
        "DDR5 32GB": 120,
        "DDR5 16GB": 70,
        "DDR4 32GB": 80,
        "DDR4 16GB": 50,
    }

    # DDR5
    assert GemRecommendationService._estimate_ram_cost(32, "DDR5", {"RAM": prices}) == 120
    assert GemRecommendationService._estimate_ram_cost(16, "DDR5", {"RAM": prices}) == 70

    # DDR4
    assert GemRecommendationService._estimate_ram_cost(32, "DDR4", {"RAM": prices}) == 80
    assert GemRecommendationService._estimate_ram_cost(16, "DDR4", {"RAM": prices}) == 50

    # None
    assert GemRecommendationService._estimate_ram_cost(None, "DDR5", {"RAM": prices}) == 0.0


@pytest.mark.asyncio
async def test_estimate_ssd_cost():
    """Test SSD cost estimation."""
    prices = {
        "Storage": {
            "1TB NVMe Gen4": 79,
            "2TB NVMe Gen4": 119,
            "1TB NVMe Gen5": 89,
            "2TB NVMe Gen5": 149,
        }
    }

    assert GemRecommendationService._estimate_ssd_cost(512, prices) == 79
    assert GemRecommendationService._estimate_ssd_cost(1000, prices) == 89
    assert GemRecommendationService._estimate_ssd_cost(2000, prices) == 149
    assert GemRecommendationService._estimate_ssd_cost(None, prices) == 0.0


@pytest.mark.asyncio
async def test_enrich_recommendation_financial(db_with_orders):
    """Test financial enrichment of recommendations."""
    db, _ = db_with_orders
    service = GemRecommendationService(db)
    market_prices = service._get_market_prices()

    rec = {
        "name": "1440p Gaming Beast",
        "use_case": "gaming",
        "target_budget_gbp": 1200,
        "specs": {
            "cpu": "Intel i7-14700K",
            "gpu": "RTX 4070",
            "ram_gb": 32,
            "ram_type": "DDR5",
            "ssd_gb": 1000,
            "psu_watts": 850,
            "case": "Fractal Design Torrent",
            "cooler": "NZXT Kraken X73",
            "motherboard": "ASUS TUF Z890",
        },
        "estimated_cost_gbp": 950,
        "estimated_market_price_gbp": 1200,
        "confidence_score": 85,
        "risk_level": "low",
        "recommended_quantity": 2,
        "reasoning": "High demand for gaming builds",
    }

    service._enrich_recommendation_financial(rec, market_prices)

    # Verify enrichment
    assert "actual_cost_to_build" in rec
    assert "actual_margin_gbp" in rec
    assert "actual_margin_percent" in rec
    assert "cost_breakdown" in rec
    assert "labor_cost" in rec
    assert "overhead_cost" in rec

    # Verify profit calculation
    assert rec["actual_cost_to_build"] > 0
    assert rec["actual_margin_gbp"] > 0
    assert rec["actual_margin_percent"] > 0
    assert rec["actual_margin_percent"] <= 100

    # Verify cost breakdown includes components
    assert len(rec["cost_breakdown"]) > 0


@pytest.mark.asyncio
async def test_store_recommendation(db_with_orders):
    """Test storing a recommendation in the database."""
    db, _ = db_with_orders
    service = GemRecommendationService(db)

    rec = {
        "name": "Test Gem Build",
        "use_case": "gaming",
        "target_budget_gbp": 1200,
        "specs": {"cpu": "i7", "gpu": "RTX 4070"},
        "actual_cost_to_build": 850,
        "estimated_market_price_gbp": 1200,
        "actual_margin_gbp": 350,
        "actual_margin_percent": 29.2,
        "confidence_score": 85,
        "reasoning": "High demand",
        "recommended_quantity": 2,
        "cost_breakdown": {"cpu": 400, "gpu": 500},
    }

    gem = await service._store_recommendation(rec, 30)

    # Verify gem was stored
    assert gem.id is not None
    assert gem.name == "Test Gem Build"
    assert gem.use_case == "gaming"
    assert gem.confidence_score == 85
    assert gem.risk_level == GemRiskLevel.LOW
    assert gem.margin_percent == 29.2
    assert gem.analysis_period_days == 30

    # Verify it can be retrieved
    retrieved = await service.get_recommendation_by_id(gem.id)
    assert retrieved is not None
    assert retrieved.name == "Test Gem Build"


@pytest.mark.asyncio
async def test_list_recommendations(db_with_orders):
    """Test listing recommendations with filtering."""
    db, _ = db_with_orders
    service = GemRecommendationService(db)

    # Add some test gems
    gems_data = [
        {"name": "Low Risk Gaming", "use_case": "gaming", "confidence_score": 90, "risk": GemRiskLevel.LOW},
        {"name": "Medium Risk Workstation", "use_case": "workstation", "confidence_score": 70, "risk": GemRiskLevel.MEDIUM},
        {"name": "High Risk Streaming", "use_case": "streaming", "confidence_score": 45, "risk": GemRiskLevel.HIGH},
    ]

    for gem_data in gems_data:
        gem = GemBuild(
            name=gem_data["name"],
            use_case=gem_data["use_case"],
            target_budget_gbp=1200,
            specs={"cpu": "i7", "gpu": "RTX 4070"},
            estimated_cost_to_build=850,
            estimated_market_price=1200,
            margin_gbp=350,
            margin_percent=29.2,
            confidence_score=gem_data["confidence_score"],
            risk_level=gem_data["risk"],
            recommended_quantity=2,
            reasoning="Test",
            cost_breakdown={},
            analysis_period_days=30,
        )
        db.add(gem)
    await db.commit()

    # Test list all
    all_gems = await service.list_recommendations()
    assert len(all_gems) >= 3

    # Test filter by risk level
    low_risk = await service.list_recommendations(risk_level="low")
    assert all(g.risk_level == GemRiskLevel.LOW for g in low_risk)

    # Test filter by use case
    gaming = await service.list_recommendations(use_case="gaming")
    assert all(g.use_case == "gaming" for g in gaming)

    # Test combined filters
    medium_workstation = await service.list_recommendations(risk_level="medium", use_case="workstation")
    assert len(medium_workstation) >= 1
    assert all(g.risk_level == GemRiskLevel.MEDIUM and g.use_case == "workstation" for g in medium_workstation)


@pytest.mark.asyncio
async def test_delete_recommendation(db_with_orders):
    """Test deleting a recommendation."""
    db, _ = db_with_orders
    service = GemRecommendationService(db)

    # Create a gem
    gem = GemBuild(
        name="Test Delete Gem",
        use_case="gaming",
        target_budget_gbp=1200,
        specs={"cpu": "i7"},
        estimated_cost_to_build=850,
        estimated_market_price=1200,
        margin_gbp=350,
        margin_percent=29.2,
        confidence_score=85,
        risk_level=GemRiskLevel.LOW,
        recommended_quantity=2,
        reasoning="Test",
        cost_breakdown={},
        analysis_period_days=30,
    )
    db.add(gem)
    await db.commit()

    gem_id = gem.id

    # Delete it
    deleted = await service.delete_recommendation(gem_id)
    assert deleted is True
    await db.commit()

    # Verify it's gone
    retrieved = await service.get_recommendation_by_id(gem_id)
    assert retrieved is None

    # Test deleting non-existent
    deleted = await service.delete_recommendation(99999)
    assert deleted is False


@pytest.mark.asyncio
@patch('app.services.gem_service.Anthropic')
async def test_call_claude_for_recommendations(mock_anthropic_class, db_with_orders):
    """Test Claude API integration (mocked)."""
    db, _ = db_with_orders
    service = GemRecommendationService(db)

    # Mock the Claude response
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    claude_response = {
        "recommendations": [
            {
                "name": "1440p Gaming Beast",
                "use_case": "gaming",
                "target_budget_gbp": 1200,
                "specs": {
                    "cpu": "Intel i7-14700K",
                    "gpu": "RTX 4070",
                    "ram_gb": 32,
                    "ram_type": "DDR5",
                    "ssd_gb": 1000,
                    "psu_watts": 850,
                    "case": "Fractal Design Torrent",
                    "cooler": "NZXT Kraken X73",
                },
                "estimated_cost_gbp": 850,
                "estimated_market_price_gbp": 1200,
                "confidence_score": 85,
                "risk_level": "low",
                "recommended_quantity": 2,
                "reasoning": "High gaming demand from market analysis",
            }
        ]
    }

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=json.dumps(claude_response))]
    mock_client.messages.create.return_value = mock_message

    demand_analysis = await service._analyze_demand(30)
    market_prices = service._get_market_prices()

    recommendations = await service._call_claude_for_recommendations(
        demand_analysis,
        market_prices,
        30
    )

    assert len(recommendations) >= 1
    assert recommendations[0]["name"] == "1440p Gaming Beast"
    assert recommendations[0]["confidence_score"] == 85


@pytest.mark.asyncio
async def test_gem_build_to_dict():
    """Test GemBuild model to_dict conversion."""
    gem = GemBuild(
        id=1,
        name="Test Gem",
        use_case="gaming",
        target_budget_gbp=1200,
        specs={"cpu": "i7", "gpu": "RTX 4070"},
        estimated_cost_to_build=850,
        estimated_market_price=1200,
        margin_gbp=350,
        margin_percent=29.2,
        confidence_score=85,
        risk_level=GemRiskLevel.LOW,
        recommended_quantity=2,
        reasoning="High demand",
        cost_breakdown={"cpu": 400},
        analysis_period_days=30,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        generated_at=datetime.utcnow(),
    )

    result = gem.to_dict()

    assert result["id"] == 1
    assert result["name"] == "Test Gem"
    assert result["margin_percent"] == 29.2
    assert result["risk_level"] == "low"
    assert isinstance(result["created_at"], str)
