from datetime import datetime, timedelta

from app.gem_radar.phase2_runner import component_alert_matches_listing
from app.models import PriceAlert


def alert(**overrides):
    values = {
        "alert_type": "component", "component_key": "AMD Ryzen 7 7800X3D",
        "component_slot": "cpu", "cpk": "cpu-cpk", "condition_cohort": "used",
        "monitoring_status": "armed", "is_active": True, "triggered_at": None,
        "user_email": "owner@example.com", "target_price_gbp": 20000,
    }
    values.update(overrides)
    return PriceAlert(**values)


def test_requires_exact_cpk_not_title_or_category():
    now = datetime.utcnow()
    assert component_alert_matches_listing(alert(), listing_cpk="cpu-cpk", listing_condition="used", observed_at=now, now=now)
    assert not component_alert_matches_listing(alert(), listing_cpk="motherboard-cpk", listing_condition="used", observed_at=now, now=now)


def test_rejects_wrong_condition_and_stale_listing():
    now = datetime.utcnow()
    assert not component_alert_matches_listing(alert(), listing_cpk="cpu-cpk", listing_condition="new", observed_at=now, now=now)
    assert not component_alert_matches_listing(alert(), listing_cpk="cpu-cpk", listing_condition="used", observed_at=now - timedelta(hours=49), now=now)


def test_pending_identity_and_triggered_alerts_never_match():
    now = datetime.utcnow()
    assert not component_alert_matches_listing(alert(cpk=None, monitoring_status="pending_identity"), listing_cpk="cpu-cpk", listing_condition="used", observed_at=now, now=now)
    assert not component_alert_matches_listing(alert(monitoring_status="triggered", triggered_at=now), listing_cpk="cpu-cpk", listing_condition="used", observed_at=now, now=now)
