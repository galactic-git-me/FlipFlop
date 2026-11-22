from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.schemas.autonomous_agents import AgentEvent
from app.services import autonomous_agent_handoffs
from app.services.playbook_management_agent import (
    PLAYBOOK_MANAGER_STALE_AFTER,
    PlaybookRefreshInProgress,
    _manager_run_is_fresh,
)


def test_manager_run_freshness_uses_heartbeat_and_recovers_stale_runs():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    assert _manager_run_is_fresh(SimpleNamespace(
        status="running", heartbeat_at=now - timedelta(seconds=30), started_at=now,
    ), now)
    assert not _manager_run_is_fresh(SimpleNamespace(
        status="running", heartbeat_at=now - PLAYBOOK_MANAGER_STALE_AFTER - timedelta(seconds=1),
        started_at=now - timedelta(hours=1),
    ), now)
    assert not _manager_run_is_fresh(SimpleNamespace(
        status="succeeded", heartbeat_at=now, started_at=now,
    ), now)


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False


@pytest.mark.asyncio
async def test_fresh_duplicate_refresh_does_not_settle_the_triggering_event(monkeypatch):
    event = AgentEvent(
        event_id="source-event-1",
        event_type="playbook_refresh_requested",
        producer="system",
        occurred_at=datetime.now(timezone.utc),
        idempotency_key="source-key-1",
    )
    monkeypatch.setattr(autonomous_agent_handoffs, "AsyncSessionLocal", _Session)
    monkeypatch.setattr(
        autonomous_agent_handoffs, "pending_agent_events", AsyncMock(return_value=[event]),
    )
    process = AsyncMock(side_effect=PlaybookRefreshInProgress("active"))
    monkeypatch.setattr(autonomous_agent_handoffs, "process_playbook_event", process)
    settle = AsyncMock()
    monkeypatch.setattr(autonomous_agent_handoffs, "mark_agent_event", settle)

    result = await autonomous_agent_handoffs.run_pending_agent_handoffs()

    assert result == {"ok": True, "handled": 0, "failed": 0}
    process.assert_awaited_once_with(event)
    settle.assert_not_awaited()


@pytest.mark.asyncio
async def test_interrupted_duplicate_does_not_emit_completion_or_mark_source_complete(monkeypatch):
    event = AgentEvent(
        event_id="source-event-2",
        event_type="playbook_refresh_requested",
        producer="system",
        occurred_at=datetime.now(timezone.utc),
        idempotency_key="source-key-2",
    )
    from app.services import playbook_management_agent

    monkeypatch.setattr(
        playbook_management_agent, "run_playbook_manager_cycle",
        AsyncMock(side_effect=PlaybookRefreshInProgress("active")), raising=False,
    )
    monkeypatch.setattr(autonomous_agent_handoffs, "mark_agent_event", AsyncMock())
    monkeypatch.setattr(autonomous_agent_handoffs, "persist_agent_event", AsyncMock())

    with pytest.raises(PlaybookRefreshInProgress):
        await autonomous_agent_handoffs.process_playbook_event(event)

    autonomous_agent_handoffs.mark_agent_event.assert_not_awaited()
    autonomous_agent_handoffs.persist_agent_event.assert_not_awaited()


@pytest.mark.asyncio
async def test_heartbeat_retries_transient_db_failures_then_stops_expired_owner(monkeypatch):
    import asyncio
    from app import database
    from app.models.playbook_refresh_run import PlaybookRefreshRun
    from app.services import agent_skill_loader, playbook_management_agent
    from app.services import playbook_service

    monkeypatch.setattr(playbook_management_agent, "PLAYBOOK_MANAGER_STALE_AFTER", timedelta(milliseconds=20))
    monkeypatch.setattr(playbook_management_agent, "PLAYBOOK_MANAGER_HEARTBEAT_SECONDS", 0.001)
    monkeypatch.setattr(agent_skill_loader, "load_agent_skill", lambda _name: "skill")

    run = None
    heartbeat_attempts = 0

    class _ManagerSession(_Session):
        async def execute(self, _statement):
            return None

        async def get(self, model, _job_id):
            nonlocal heartbeat_attempts
            if model is PlaybookRefreshRun:
                heartbeat_attempts += 1
                if heartbeat_attempts == 1:
                    return run
                raise RuntimeError("temporary database outage")
            return None

        def add(self, value):
            nonlocal run
            run = value

        async def commit(self):
            return None

    monkeypatch.setattr(database, "AsyncSessionLocal", _ManagerSession)
    refresh_started = asyncio.Event()
    refresh_cancelled = asyncio.Event()

    async def blocked_refresh(*_args, **_kwargs):
        refresh_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            refresh_cancelled.set()
            raise

    monkeypatch.setattr(playbook_service, "refresh_playbooks", blocked_refresh)
    event = AgentEvent(
        event_id="source-event-heartbeat",
        event_type="playbook_refresh_requested",
        producer="system",
        occurred_at=datetime.now(timezone.utc),
        idempotency_key="source-key-heartbeat",
    )

    with pytest.raises(asyncio.CancelledError):
        await playbook_management_agent.run_playbook_manager_cycle(event)

    assert refresh_started.is_set()
    assert refresh_cancelled.is_set()
    assert heartbeat_attempts > 1
