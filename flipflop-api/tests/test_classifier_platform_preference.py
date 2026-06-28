from app.services.classifier import score_listing


def _score(title: str, ram_type: str) -> float:
    result = score_listing(
        title=title,
        price=220.0,
        estimated_profit=120.0,
        cpu="Ryzen 7",
        ram_gb=16,
        ram_type=ram_type,
        storage_gb=1000,
        gpu="RTX 3060",
        has_psu=True,
        location="UK",
        profit_low=80.0,
        profit_high=160.0,
    )
    return result.score


def test_am4_ddr4_scores_higher_than_am5_ddr5_when_otherwise_equal():
    am4_score = _score("Gaming PC Ryzen 7 B550 AM4 bundle", "DDR4")
    am5_score = _score("Gaming PC Ryzen 7 B650 AM5 bundle", "DDR5")
    assert am4_score > am5_score


def test_am5_ddr5_is_still_scored_not_excluded():
    am5 = score_listing(
        title="Gaming PC Ryzen 7 B650 AM5 bundle",
        price=220.0,
        estimated_profit=120.0,
        cpu="Ryzen 7",
        ram_gb=16,
        ram_type="DDR5",
        storage_gb=1000,
        gpu="RTX 3060",
        has_psu=True,
        location="UK",
        profit_low=80.0,
        profit_high=160.0,
    )
    assert am5.score > 0

