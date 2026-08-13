from datetime import datetime, timedelta

from app.services.offer_engine import evaluate_buyer_offer, evaluate_send_to_watchers


def test_offers_disabled_declines():
    result = evaluate_buyer_offer(
        buyer_offer=400.0, listing_price=500.0, min_offer_price=420.0,
        offers_enabled=False, counter_offer_round=0, last_counter_offer_price=None,
    )
    assert result.action == "decline"


def test_rule1_first_counter_is_midpoint():
    result = evaluate_buyer_offer(
        buyer_offer=440.0, listing_price=500.0, min_offer_price=420.0,
        offers_enabled=True, counter_offer_round=0, last_counter_offer_price=None,
    )
    assert result.action == "counter"
    assert result.counter_price == 470.0  # (440+500)/2


def test_rule2_second_counter_is_five_off():
    result = evaluate_buyer_offer(
        buyer_offer=460.0, listing_price=500.0, min_offer_price=420.0,
        offers_enabled=True, counter_offer_round=1, last_counter_offer_price=470.0,
    )
    assert result.action == "counter"
    assert result.counter_price == 465.0


def test_no_third_round():
    result = evaluate_buyer_offer(
        buyer_offer=460.0, listing_price=500.0, min_offer_price=420.0,
        offers_enabled=True, counter_offer_round=2, last_counter_offer_price=465.0,
    )
    assert result.action == "no_further_rounds"


def test_below_tolerance_still_gets_a_counter_not_silence():
    # Row 8: always respond, even to a lowball, to keep the engagement signal alive.
    result = evaluate_buyer_offer(
        buyer_offer=200.0, listing_price=500.0, min_offer_price=420.0,
        offers_enabled=True, counter_offer_round=0, last_counter_offer_price=None,
    )
    assert result.action == "counter"
    assert result.counter_price is not None


def test_watchers_not_sent_before_threshold():
    plan = evaluate_send_to_watchers(
        listing_price=500.0, min_offer_price=420.0,
        listed_at=datetime.utcnow() - timedelta(days=2),
        last_watcher_offer_sent_at=None,
    )
    assert plan.should_send is False


def test_watchers_sent_after_threshold():
    plan = evaluate_send_to_watchers(
        listing_price=500.0, min_offer_price=420.0,
        listed_at=datetime.utcnow() - timedelta(days=6),
        last_watcher_offer_sent_at=None,
    )
    assert plan.should_send is True
    assert plan.offer_price == 450.0  # 10% off, above the min-offer floor


def test_watchers_respect_min_offer_floor():
    plan = evaluate_send_to_watchers(
        listing_price=460.0, min_offer_price=430.0,
        listed_at=datetime.utcnow() - timedelta(days=6),
        last_watcher_offer_sent_at=None,
    )
    assert plan.offer_price >= 430.0


def test_watchers_respect_twice_daily_cadence():
    plan = evaluate_send_to_watchers(
        listing_price=500.0, min_offer_price=420.0,
        listed_at=datetime.utcnow() - timedelta(days=6),
        last_watcher_offer_sent_at=datetime.utcnow() - timedelta(hours=2),
    )
    assert plan.should_send is False
