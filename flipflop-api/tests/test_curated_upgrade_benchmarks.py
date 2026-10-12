from types import SimpleNamespace

import pytest

from app.api.curated_builds import _upgrade_performance_evidence


def _benchmark(
    component_type: str,
    model: str,
    *,
    gaming: float,
    overall: float | None = None,
    workstation: float | None = None,
):
    return SimpleNamespace(
        component_type=component_type,
        normalized_model=model,
        confidence_score=0.9,
        gaming_score=gaming,
        workstation_score=workstation if workstation is not None else gaming,
        overall_score=overall if overall is not None else gaming,
        model=model,
        benchmark_source="test-source",
    )


def test_gaming_cell_accepts_equal_or_better_gpu_and_returns_evidence(monkeypatch):
    monkeypatch.setattr("app.api.curated_builds.normalise_gpu", lambda value: value.casefold())
    evidence = _upgrade_performance_evidence(
        component_type="gpu",
        baseline_model="Baseline GPU",
        candidate_model="Upgrade GPU",
        customer_type="Great-value Gaming",
        benchmark_rows=[
            _benchmark("gpu", "baseline gpu", gaming=100),
            _benchmark("gpu", "upgrade gpu", gaming=100),
        ],
    )

    assert evidence["metric"] == "gaming_score"
    assert evidence["candidate_score"] == evidence["baseline_score"] == 100


def test_creator_cell_rejects_worse_cpu_even_if_overall_is_higher(monkeypatch):
    monkeypatch.setattr("app.api.curated_builds.normalise_cpu", lambda value: value.casefold())
    with pytest.raises(ValueError, match="scores below this PlayBook cell's baseline"):
        _upgrade_performance_evidence(
            component_type="cpu",
            baseline_model="Baseline CPU",
            candidate_model="Upgrade CPU",
            customer_type="Content Creator",
            benchmark_rows=[
            _benchmark("cpu", "baseline cpu", gaming=50, overall=90, workstation=50),
            _benchmark("cpu", "upgrade cpu", gaming=80, overall=89, workstation=40),
            ],
        )


def test_missing_cpu_benchmark_evidence_fails_closed(monkeypatch):
    monkeypatch.setattr("app.api.curated_builds.normalise_cpu", lambda value: value.casefold())
    with pytest.raises(ValueError, match="benchmark evidence is missing"):
        _upgrade_performance_evidence(
            component_type="cpu",
            baseline_model="Baseline CPU",
            candidate_model="Upgrade CPU",
            customer_type="Office Workstation",
            benchmark_rows=[_benchmark("cpu", "baseline cpu", gaming=50)],
        )
