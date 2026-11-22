import asyncio
from datetime import datetime, timedelta, timezone

from app.api import gem_radar
from app.services.runtime_heartbeats import (
    configure_worker_heartbeats,
    record_worker_heartbeat,
    worker_heartbeat_status,
)


def test_worker_heartbeat_reports_each_expected_worker():
    service = "test-gem-radar"
    configure_worker_heartbeats(service, 2)
    record_worker_heartbeat(service, "0")

    partial = worker_heartbeat_status(service)
    assert partial["ok"] is False
    assert partial["online_workers"] == 1
    assert partial["expected_workers"] == 2

    record_worker_heartbeat(service, "1")
    healthy = worker_heartbeat_status(service)
    assert healthy["ok"] is True
    assert healthy["online_workers"] == 2
    assert healthy["last_heartbeat_at"] is not None


def test_extension_heartbeat_is_per_environment_and_expires(monkeypatch):
    monkeypatch.setattr(gem_radar, "_extension_status_by_environment", {})
    payload = gem_radar.ExtensionHeartbeatIn(
        state="scanning",
        activeSearches=3,
        searchesCompleted=8,
        extensionVersion="1.2.3",
        environment="DEV",
    )

    asyncio.run(gem_radar.update_extension_heartbeat(payload))
    dev = asyncio.run(gem_radar.extension_status("DEV"))
    live = asyncio.run(gem_radar.extension_status("LIVE"))

    assert dev.state == "scanning"
    assert dev.activeSearches == 3
    assert dev.extensionVersion == "1.2.3"
    assert live.state == "offline"

    expired = dev.model_copy(update={"lastHeartbeat": datetime.now(timezone.utc) - timedelta(minutes=4)})
    monkeypatch.setitem(gem_radar._extension_status_by_environment, "DEV", expired)
    assert asyncio.run(gem_radar.extension_status("DEV")).state == "offline"


def test_product_detail_routes_are_registered():
    paths = {route.path for route in gem_radar.router.routes}
    assert "/gem-radar/ebay-item-details" in paths
    assert "/gem-radar/amazon-item-details" in paths
    assert "/gem-radar/extension-status/heartbeat" in paths
