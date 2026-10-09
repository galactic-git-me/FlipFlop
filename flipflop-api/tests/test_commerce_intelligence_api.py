from app.api.commerce_intelligence import (
    GemAssessmentRequest, PriceAssessmentRequest, gem_assessment, price_assessment,
)


def test_admin_assessment_returns_non_offer_when_market_is_missing():
    body = PriceAssessmentRequest(
        costs={
            "landed_parts": "500", "build_labour": "80", "packaging": "10",
            "outbound_delivery": "20", "payment_cost": "20", "warranty_reserve": "20",
            "returns_reserve": "10", "expected_failure_cost": "10", "allocated_overhead": "30",
        },
        market={"condition": "new", "sold_median_gbp": None, "sold_sample_size": 0},
        condition="new", minimum_contribution_gbp="100", minimum_margin_fraction="0.15",
    )
    result = price_assessment(body)
    assert result["offerable"] is False
    assert result["status"] == "assessment_only"


def test_admin_gem_assessment_never_authorises_autonomous_purchase():
    body = GemAssessmentRequest(
        costs={
            "asking_price": "100", "inbound_delivery": "10", "buyer_protection": "5",
            "repairs_and_upgrades": "30", "build_labour": "20", "outbound_delivery": "15",
            "marketplace_fees": "25", "warranty_and_returns_reserve": "10", "risk_reserve": "10",
        },
        conservative_resale_gbp="300", minimum_net_contribution_gbp="50",
        estimated_days_to_sell=20, remaining_speculative_budget_gbp="120", sold_sample_size=5,
    )
    assert gem_assessment(body)["autonomous_purchase_allowed"] is False
