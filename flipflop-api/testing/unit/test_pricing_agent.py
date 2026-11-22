from datetime import datetime, timezone

from app.schemas.autonomous_agents import AgentEvent
from app.services.pricing_agent import _pricing_correlation_id


def test_pricing_event_uses_bounded_deterministic_correlation_id():
    idempotency_key = "component-price-change:" + ("a" * 200)

    correlation_id = _pricing_correlation_id(idempotency_key)
    event = AgentEvent(
        event_type="component_market_price_changed",
        producer="pricing",
        occurred_at=datetime.now(timezone.utc),
        idempotency_key=idempotency_key,
        correlation_id=correlation_id,
    )

    assert len(event.correlation_id) <= 64
    assert event.correlation_id == _pricing_correlation_id(idempotency_key)
