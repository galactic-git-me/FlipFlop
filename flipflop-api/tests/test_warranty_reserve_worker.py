"""Unexecuted regression coverage for atomic warranty-expiry alerts."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.models.alert_event import AlertEvent
from app.workers import warranty_reserve


class _FakeSession:
    def __init__(self, reserves):
        self.reserves = reserves
        self.added = []
        self.commit_count = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def execute(self, _statement):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: self.reserves))

    def add(self, item):
        self.added.append(item)

    async def commit(self):
        self.commit_count += 1


@pytest.mark.asyncio
async def test_expiry_eligibility_and_admin_alert_commit_together(monkeypatch):
    reserve = SimpleNamespace(
        id=42,
        warranty_expires_at=datetime.utcnow() - timedelta(days=1),
        status="held",
        expiry_alerted_at=None,
        reserved_amount_gbp=100.0,
        allocated_claim_amount_gbp=15.0,
    )
    session = _FakeSession([42])
    monkeypatch.setattr(warranty_reserve, "AsyncSessionLocal", lambda: session)

    async def lock_reserve(_db, reserve_id, *, skip_locked):
        assert reserve_id == 42
        assert skip_locked is True
        return reserve

    monkeypatch.setattr(warranty_reserve, "lock_warranty_owner_then_reserve", lock_reserve)

    async def mark_eligible(_db, current):
        current.status = "eligible_for_release"
        return current.status

    monkeypatch.setattr(warranty_reserve, "recalculate_reserve_status", mark_eligible)

    result = await warranty_reserve.run_warranty_reserve_job()

    assert result == {"ok": True, "eligible_alerts": 1, "expired_checked": 1}
    assert reserve.expiry_alerted_at is not None
    assert session.commit_count == 1
    assert len(session.added) == 1
    alert = session.added[0]
    assert isinstance(alert, AlertEvent)
    assert alert.code == "warranty_reserve_eligible_42"
    assert "£85.00" in alert.message


@pytest.mark.asyncio
async def test_open_claim_does_not_create_expiry_alert(monkeypatch):
    reserve = SimpleNamespace(
        id=43,
        warranty_expires_at=datetime.utcnow() - timedelta(days=1),
        status="held",
        expiry_alerted_at=None,
        reserved_amount_gbp=100.0,
        allocated_claim_amount_gbp=0.0,
    )
    session = _FakeSession([43])
    monkeypatch.setattr(warranty_reserve, "AsyncSessionLocal", lambda: session)

    async def lock_reserve(_db, reserve_id, *, skip_locked):
        assert reserve_id == 43
        assert skip_locked is True
        return reserve

    monkeypatch.setattr(warranty_reserve, "lock_warranty_owner_then_reserve", lock_reserve)

    async def retain_claim_hold(_db, current):
        current.status = "claim_open"
        return current.status

    monkeypatch.setattr(warranty_reserve, "recalculate_reserve_status", retain_claim_hold)

    result = await warranty_reserve.run_warranty_reserve_job()

    assert result == {"ok": True, "eligible_alerts": 0, "expired_checked": 1}
    assert reserve.expiry_alerted_at is None
    assert session.added == []
    assert session.commit_count == 1


@pytest.mark.asyncio
async def test_expiry_worker_rechecks_released_reserve_after_lock(monkeypatch):
    reserve = SimpleNamespace(
        id=44,
        warranty_expires_at=datetime.utcnow() - timedelta(days=1),
        status="released",
        expiry_alerted_at=None,
        reserved_amount_gbp=100.0,
        allocated_claim_amount_gbp=0.0,
    )
    session = _FakeSession([44])
    monkeypatch.setattr(warranty_reserve, "AsyncSessionLocal", lambda: session)

    async def lock_reserve(_db, reserve_id, *, skip_locked):
        assert reserve_id == 44
        assert skip_locked is True
        return reserve

    async def unexpected_recalculation(*_args, **_kwargs):
        raise AssertionError("A released reserve must not be recalculated")

    monkeypatch.setattr(warranty_reserve, "lock_warranty_owner_then_reserve", lock_reserve)
    monkeypatch.setattr(warranty_reserve, "recalculate_reserve_status", unexpected_recalculation)

    result = await warranty_reserve.run_warranty_reserve_job()

    assert result == {"ok": True, "eligible_alerts": 0, "expired_checked": 0}
    assert session.added == []
    assert session.commit_count == 1
