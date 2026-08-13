"""Pure-function tests for the Gem Radar scoring engine — no DB, no network.
Fixture library modelled on PRD §44 (excellent deal, at-market, parts-only
trap, thin sample).
"""
from datetime import datetime, timezone

import pytest

from app.gem_radar.identity import resolve_identity
from app.gem_radar.risk import detect_risk_flags, risk_penalty
from app.gem_radar.scoring import classify, compute_deal_score, compute_decision, pick_condition_benchmark
from app.gem_radar.schemas import BenchmarkStat, ExtractedListing, PriceBundle, RiskFlag


def _bench(median: float, n: int = 10) -> BenchmarkStat:
    return BenchmarkStat(
        status="ok",
        average=median,
        median=median,
        trimmedMean=median,
        min=median * 0.8,
        max=median * 1.2,
        sampleSize=n,
        validSampleSize=n,
        matchLevelCounts={"exact_model_variant": n},
        exclusions=[],
        source="test",
        sourceUrl=None,
        observedAt=datetime.now(timezone.utc),
        ageMinutes=5.0,
    )


def _unavailable() -> BenchmarkStat:
    return BenchmarkStat(
        status="unavailable",
        average=None,
        median=None,
        trimmedMean=None,
        min=None,
        max=None,
        sampleSize=0,
        validSampleSize=0,
        matchLevelCounts={},
        exclusions=[],
        source="test",
        sourceUrl=None,
        observedAt=None,
        ageMinutes=None,
        unavailableReason="no data",
    )


def _listing(price: float, condition: str = "used", feedback: float | None = 99.9, title: str = "Ryzen 7 5700X") -> ExtractedListing:
    return ExtractedListing(
        listingId="1",
        url="https://www.ebay.co.uk/itm/1",
        title=title,
        seller="seller1",
        sellerFeedbackPercent=feedback,
        sellerFeedbackCount=500,
        conditionRaw=condition,
        conditionNormalised=condition,
        itemPrice=price,
        postagePrice=0,
        currentDeliveredPrice=price,
        listingType="buy_it_now",
        bestOfferEnabled=False,
        bidCount=None,
        auctionEndAt=None,
        imageUrl="http://x",
        sponsored=False,
        extractedAt=datetime.now(timezone.utc),
    )


class TestClassificationBoundaries:
    @pytest.mark.parametrize(
        "score,expected",
        [(10.0, "SUPER_GEM"), (9.0, "SUPER_GEM"), (8.99, "GEM"), (8.0, "GEM"), (7.99, "OK_DEAL"), (7.0, "OK_DEAL"), (6.99, "AVERAGE_DEAL"), (5.0, "AVERAGE_DEAL"), (4.99, "POOR_DEAL"), (0.0, "POOR_DEAL")],
    )
    def test_exact_boundaries(self, score, expected):
        assert classify(score) == expected


class TestDealScore:
    def test_at_market_price_is_not_a_gem(self):
        prices = PriceBundle(
            actualListing=128, ebayNewBin=_unavailable(), ebayUsedBin=_bench(100), ebayNewSold=_unavailable(),
            ebayUsedSold=_bench(128), amazonUkNew=_unavailable(),
        )
        score, _ = compute_deal_score(_listing(128), prices, risk_penalty=0.0)
        assert classify(score) in ("AVERAGE_DEAL", "POOR_DEAL")

    def test_score_increases_monotonically_as_price_drops(self):
        prices_at = lambda p: PriceBundle(  # noqa: E731
            actualListing=p, ebayNewBin=_unavailable(), ebayUsedBin=_bench(100), ebayNewSold=_unavailable(),
            ebayUsedSold=_bench(128), amazonUkNew=_unavailable(),
        )
        scores = [compute_deal_score(_listing(p), prices_at(p), risk_penalty=0.0)[0] for p in [128, 100, 80, 60, 40]]
        assert scores == sorted(scores)

    def test_deep_discount_with_strong_evidence_reaches_super_gem(self):
        prices = PriceBundle(
            actualListing=30, ebayNewBin=_unavailable(), ebayUsedBin=_bench(100), ebayNewSold=_unavailable(),
            ebayUsedSold=_bench(128), amazonUkNew=_unavailable(),
        )
        score, _ = compute_deal_score(_listing(30), prices, risk_penalty=0.0)
        assert classify(score) == "SUPER_GEM"

    def test_risk_penalty_pulls_score_down(self):
        prices = PriceBundle(
            actualListing=45, ebayNewBin=_unavailable(), ebayUsedBin=_bench(100), ebayNewSold=_unavailable(),
            ebayUsedSold=_bench(128), amazonUkNew=_unavailable(),
        )
        clean, _ = compute_deal_score(_listing(45), prices, risk_penalty=0.0)
        risky, _ = compute_deal_score(_listing(45), prices, risk_penalty=3.0)
        assert risky < clean

    def test_parts_only_never_benchmarks_against_working_used_value(self):
        # PRD §13.3 / non-negotiable rule #12: never treat parts-only as working used.
        prices = PriceBundle(
            actualListing=40, ebayNewBin=_unavailable(), ebayUsedBin=_bench(100), ebayNewSold=_unavailable(),
            ebayUsedSold=_unavailable(), amazonUkNew=_unavailable(),
        )
        stat, label = pick_condition_benchmark("parts_only", prices)
        assert "parts_or_untested" in label
        assert stat is not prices.ebay_used_bin  # must not silently fall back to used BIN


class TestRiskFlags:
    def test_parts_only_flagged_high_severity(self):
        flags = detect_risk_flags("Ryzen 5600 CPU - for parts or not working", None)
        codes = {f.code for f in flags}
        assert "PARTS_ONLY" in codes
        assert any(f.severity == "high" for f in flags if f.code == "PARTS_ONLY")

    def test_multiple_flags_detected_without_duplicates(self):
        flags = detect_risk_flags("Untested, bent pins, sold as seen, no returns", None)
        codes = [f.code for f in flags]
        assert len(codes) == len(set(codes))
        assert "UNTESTED" in codes
        assert "SOCKET_DAMAGE" in codes
        assert "SOLD_AS_SEEN" in codes
        assert "NO_RETURNS" in codes

    def test_penalty_is_capped(self):
        many_flags = [RiskFlag(code=f"X{i}", severity="high", evidence="x") for i in range(10)]
        assert risk_penalty(many_flags) <= 4.0

    def test_clean_listing_has_no_flags(self):
        flags = detect_risk_flags("Corsair Vengeance RGB Pro 16GB DDR4-3200 CL16", None)
        assert flags == []


class TestIdentityResolution:
    def test_resolves_known_cpu(self):
        result = resolve_identity("AMD Ryzen 7 5700X 8-Core CPU Processor AM4 Socket")
        assert result.category == "cpu"
        assert result.model is not None
        assert result.exact_sku_confidence > 0

    def test_unresolvable_title_returns_zero_confidence_not_a_guess(self):
        result = resolve_identity("Mystery box of assorted computer bits")
        assert result.exact_sku_confidence == 0.0
        assert result.model is None


class TestDecision:
    def test_high_risk_gem_becomes_investigate_not_buy_now(self):
        # PRD §15.1 — a 9+ score is BUY_NOW only "subject to explicit hard blockers".
        flags = [RiskFlag(code="LIQUID_DAMAGE", severity="high", evidence="water damage")]
        assert compute_decision("SUPER_GEM", "high", flags) == "INVESTIGATE"

    def test_super_gem_high_confidence_no_risk_is_buy_now(self):
        assert compute_decision("SUPER_GEM", "high", []) == "BUY_NOW"

    def test_poor_deal_is_always_ignore(self):
        assert compute_decision("POOR_DEAL", "high", []) == "IGNORE"
