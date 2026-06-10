from app.services.benchmark_scorer import (
    score_ram,
    calc_performance_per_pound,
    calc_cpu_opportunity_score,
    calc_gpu_opportunity_score,
    is_gem_candidate,
    NEGATIVE_KEYWORDS,
)

def test_score_ram_ddr5_beats_ddr4():
    ddr5 = score_ram(generation="DDR5", capacity_gb=32, speed_mts=6000, cas_latency=30, dual_channel=True)
    ddr4 = score_ram(generation="DDR4", capacity_gb=32, speed_mts=3200, cas_latency=16, dual_channel=True)
    assert ddr5 > ddr4

def test_score_ram_dual_channel_bonus():
    dual = score_ram("DDR4", 32, 3200, 16, dual_channel=True)
    single = score_ram("DDR4", 32, 3200, 16, dual_channel=False)
    assert dual > single

def test_score_ram_capacity_scales():
    s32 = score_ram("DDR4", 32, 3200, 16, dual_channel=True)
    s16 = score_ram("DDR4", 16, 3200, 16, dual_channel=True)
    assert s32 > s16

def test_calc_performance_per_pound_basic():
    ppp = calc_performance_per_pound(benchmark_score=34000.0, price=195.0)
    assert abs(ppp - 174.36) < 1.0

def test_calc_performance_per_pound_zero_price():
    assert calc_performance_per_pound(10000.0, 0.0) == 0.0

def test_calc_cpu_opportunity_score_returns_0_to_100():
    score = calc_cpu_opportunity_score(
        performance_per_pound=174.0,
        marketability_score=80.0,
        demand_score=75.0,
        upgradeability_score=60.0,
        liquidity_score=70.0,
    )
    assert 0.0 <= score <= 100.0

def test_is_gem_candidate_true_when_cheap_and_performant():
    result = is_gem_candidate(
        component_price=195.0,
        avg_sold_price=245.0,
        performance_per_pound=174.0,
        category_avg_ppp=120.0,
    )
    assert result is True

def test_is_gem_candidate_false_when_overpriced():
    result = is_gem_candidate(
        component_price=250.0,
        avg_sold_price=245.0,
        performance_per_pound=90.0,
        category_avg_ppp=120.0,
    )
    assert result is False

def test_negative_keywords_list():
    assert "box only" in NEGATIVE_KEYWORDS
    assert "faulty" in NEGATIVE_KEYWORDS
