from datetime import datetime, timedelta

from app.services.pricing_engine import (
    compute_price_floor,
    compute_active_range_ceiling,
    compute_bin_anchor,
    compute_next_drop_price,
    is_drop_due,
    bias_from_fast_sale,
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
