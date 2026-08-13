from datetime import datetime, timedelta

from app.services.pricing_engine import (
    compute_price_floor,
    compute_active_range_ceiling,
    compute_bin_anchor,
    compute_next_drop_price,
    is_drop_due,
    bias_from_fast_sale,
    estimate_build_weight_kg,
    estimate_shipping_cost,
    shipping_inclusive_price,
    suggest_promoted_ad_rate,
)


def test_price_floor_is_cost_plus_min_margin():
    assert compute_price_floor(1000.0) == 1100.0
    assert compute_price_floor(500.0, min_margin_pct=0.20) == 600.0


def test_active_range_ceiling_excludes_top_outliers():
    prices = [100, 110, 115, 120, 125, 130, 500]  # 500 is an outlier
    ceiling = compute_active_range_ceiling(prices)
    assert ceiling < 500
    assert ceiling in prices


def test_active_range_ceiling_empty_returns_none():
    assert compute_active_range_ceiling([]) is None


def test_bin_anchor_uses_ceiling_when_offers_enabled():
    # Row 19: offers on -> anchor near ceiling, not at the sold-comp target
    anchor = compute_bin_anchor(sold_comp_target=800.0, active_range_ceiling=950.0, offers_enabled=True)
    assert anchor == 950.0


def test_bin_anchor_uses_sold_comp_when_offers_disabled():
    anchor = compute_bin_anchor(sold_comp_target=800.0, active_range_ceiling=950.0, offers_enabled=False)
    assert anchor == 800.0


def test_next_drop_price_never_below_floor():
    price, floor_hit = compute_next_drop_price(
        current_price=600.0, sold_comp_target=500.0, price_floor=580.0, step_pct=0.10
    )
    assert price >= 580.0
    assert floor_hit is True


def test_next_drop_price_steps_toward_target_not_past_it():
    price, floor_hit = compute_next_drop_price(
        current_price=1000.0, sold_comp_target=900.0, price_floor=700.0, step_pct=0.03
    )
    assert price == 970.0
    assert floor_hit is False


def test_drop_due_when_never_recalculated():
    assert is_drop_due(None) is True


def test_drop_due_respects_window():
    assert is_drop_due(datetime.utcnow() - timedelta(days=3), window_days=7) is False
    assert is_drop_due(datetime.utcnow() - timedelta(days=8), window_days=7) is True


def test_fast_sale_biases_next_anchor_up():
    signal = bias_from_fast_sale(days_to_sell=1, sale_price=1000.0, listing_price=1000.0)
    assert signal.was_fast_or_near_asking is True
    assert signal.suggested_anchor_bias_pct > 0


def test_slow_sale_no_bias():
    signal = bias_from_fast_sale(days_to_sell=20, sale_price=700.0, listing_price=1000.0)
    assert signal.was_fast_or_near_asking is False
    assert signal.suggested_anchor_bias_pct == 0.0


def test_build_weight_heavier_with_gpu():
    assert estimate_build_weight_kg(has_gpu=True) > estimate_build_weight_kg(has_gpu=False)


def test_shipping_cost_increases_with_weight():
    assert estimate_shipping_cost(8.0) < estimate_shipping_cost(18.0) < estimate_shipping_cost(25.0)


def test_shipping_inclusive_price_bakes_in_cost():
    result = shipping_inclusive_price(base_price=900.0, has_gpu=True)
    assert result["shipping_inclusive_price"] == 900.0 + result["estimated_shipping_cost"]
    assert result["estimated_weight_kg"] == 12.0  # 10 base + 2 GPU


def test_ad_rate_suggested_for_healthy_margin():
    result = suggest_promoted_ad_rate(estimated_profit=200.0, total_cost=800.0)  # 25% margin
    assert result["too_thin_to_promote"] is False
    assert result["suggested_ad_rate_pct"] == 0.05
    assert result["max_ad_spend"] == 30.0  # 15% of 200


def test_ad_rate_flags_thin_margin():
    result = suggest_promoted_ad_rate(estimated_profit=20.0, total_cost=800.0)  # 2.5% margin
    assert result["too_thin_to_promote"] is True
    assert result["suggested_ad_rate_pct"] == 0.0
