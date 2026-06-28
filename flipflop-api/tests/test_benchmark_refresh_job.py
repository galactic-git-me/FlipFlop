from datetime import datetime, timedelta
from app.services.benchmark_refresh_job import (
    is_benchmark_stale,
    build_active_model_list,
)

def test_is_stale_when_never_refreshed():
    assert is_benchmark_stale(last_refreshed_at=None, staleness_days=30) is True

def test_is_stale_when_old():
    old = (datetime.utcnow() - timedelta(days=31)).isoformat()
    assert is_benchmark_stale(last_refreshed_at=old, staleness_days=30) is True

def test_is_not_stale_when_recent():
    recent = (datetime.utcnow() - timedelta(days=5)).isoformat()
    assert is_benchmark_stale(last_refreshed_at=recent, staleness_days=30) is False

def test_build_active_model_list_deduplicates():
    models = build_active_model_list(
        playbook_models=["Ryzen 7 7800X3D", "Ryzen 7 7800X3D", "RTX 3070"],
        listing_models=["RTX 3070", "i7-13700K"],
    )
    assert len(models) == len(set(m.raw for m in models))
