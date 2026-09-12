from types import SimpleNamespace

from app.services.hardware_performance import enrich_listing_performance, index_benchmarks


def benchmark(model, normalized_model, score, category="gpu"):
    return SimpleNamespace(
        component_type=category,
        model=model,
        normalized_model=normalized_model,
        overall_score=score,
        gaming_score=score - 10,
        workstation_score=score - 20,
        benchmark_source="passmark",
        source_url="https://example.test/benchmark",
        last_refreshed_at="2026-09-01T00:00:00",
        confidence_score=0.8,
    )


def test_enriches_title_match_with_rank_percentile_and_value():
    rows = [
        benchmark("RTX 3060", "nvidia_geforce_rtx_3060", 6000),
        benchmark("RTX 4070", "nvidia_geforce_rtx_4070", 9000),
        benchmark("RTX 4090", "nvidia_geforce_rtx_4090", 12000),
    ]
    result = enrich_listing_performance(
        category="gpu", title="NVIDIA GeForce RTX 4070 12GB", canonical_model_id=None,
        release_year=None, delivered_price=300, benchmark_index=index_benchmarks(rows),
        peer_scores={"gpu": [6000, 9000, 12000]},
    )
    assert result["performance_status"] == "MATCHED"
    assert result["performance_match_method"] == "title_model"
    assert result["performance_rank"] == 2
    assert result["performance_percentile"] == 66.7
    assert result["performance_per_pound"] == 30.0


def test_unmatched_hardware_is_explicitly_flagged():
    result = enrich_listing_performance(
        category="gpu", title="Mystery Super Geks 8GB", canonical_model_id=None,
        release_year=None, delivered_price=40, benchmark_index={}, peer_scores={"gpu": []},
    )
    assert result == {
        "performance_status": "UNMATCHED",
        "performance_fit": "UNKNOWN",
        "performance_decision": "VERIFY_MODEL",
    }


def test_old_release_is_not_presented_as_a_modern_gem():
    row = benchmark("GTX 750", "nvidia_geforce_gtx_750", 2000)
    result = enrich_listing_performance(
        category="gpu", title="GTX 750", canonical_model_id="GTX 750",
        release_year=2014, delivered_price=25, benchmark_index=index_benchmarks([row]),
        peer_scores={"gpu": [2000]},
    )
    assert result["performance_fit"] == "LEGACY_OR_ENTRY"
    assert result["performance_decision"] == "AVOID_FOR_MODERN_BUILDS"

