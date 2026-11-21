from app.services.classifier import score_listing

def test_high_ppp_cpu_boosts_gem_score():
    result_with = score_listing(
        title="Gaming PC Ryzen 7 7800X3D RTX 3070",
        price=195.0,
        estimated_profit=120.0,
        cpu="Ryzen 7 7800X3D",
        ram_gb=32,
        ram_type="DDR5",
        storage_gb=1000,
        gpu="RTX 3070",
        has_psu=True,
        location="UK",
        profit_low=80.0,
        profit_high=160.0,
        benchmark_data={
            "cpu_overall_score": 34000,
            "cpu_performance_per_pound": 174.0,
            "category_avg_ppp": 100.0,
        },
    )
    result_without = score_listing(
        title="Gaming PC Ryzen 7 7800X3D RTX 3070",
        price=195.0,
        estimated_profit=120.0,
        cpu="Ryzen 7 7800X3D",
        ram_gb=32,
        ram_type="DDR5",
        storage_gb=1000,
        gpu="RTX 3070",
        has_psu=True,
        location="UK",
        profit_low=80.0,
        profit_high=160.0,
    )
    assert result_with.score >= result_without.score
    assert any("performance/£" in s for s in result_with.signals)
