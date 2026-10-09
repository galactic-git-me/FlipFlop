from decimal import Decimal as D

from app.services.gem_economics import GemCosts, assess_gem


def test_gem_max_buy_includes_work_fees_risk_and_capital_limit():
    costs = GemCosts(D("100"), D("10"), D("5"), D("30"), D("20"), D("15"), D("25"), D("10"), D("10"))
    result = assess_gem(costs, D("300"), D("50"), 20, D("120"), sold_sample_size=5)
    assert result["all_in_cost_gbp"] == D("225.00")
    assert result["net_contribution_gbp"] == D("75.00")
    assert result["max_buy_price_gbp"] == D("120.00")
    assert result["decision"] == "review"
    assert result["autonomous_purchase_allowed"] is False


def test_gem_without_sold_evidence_is_not_a_buy_signal():
    costs = GemCosts(D("100"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"), D("0"))
    result = assess_gem(costs, D("300"), D("50"), None, D("1000"), sold_sample_size=0)
    assert result["decision"] == "ignore"
    assert result["confidence"] == "insufficient_evidence"
