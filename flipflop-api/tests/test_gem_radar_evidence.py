"""Tests for SCREENED.json / latest_gems.json output and retention cleanup
(PRD §32-34). Evidence PDF capture itself needs a real Chromium + network
call, so it is not exercised here — these tests cover the pure filesystem
logic, which is what the retention/duplicate-artifact correctness actually
depends on.
"""
import json
import time
from datetime import datetime, timezone

import pytest

import app.gem_radar.evidence as evidence
from app.gem_radar.schemas import BenchmarkStat, ExtractedListing, Identity, PriceBundle, ScoredListing


def _unavailable() -> BenchmarkStat:
    return BenchmarkStat(
        status="unavailable", average=None, median=None, trimmedMean=None, min=None, max=None,
        sampleSize=0, validSampleSize=0, matchLevelCounts={}, exclusions=[], source="x", sourceUrl=None,
        observedAt=None, ageMinutes=None, unavailableReason="no data",
    )


def _scored_listing(listing_id: str, classification: str, deal_score: float) -> ScoredListing:
    listing = ExtractedListing(
        listingId=listing_id, url=f"https://www.ebay.co.uk/itm/{listing_id}", title="Test item", seller="s",
        sellerFeedbackPercent=99.0, sellerFeedbackCount=10, conditionRaw="Used", conditionNormalised="used",
        itemPrice=50, postagePrice=0, currentDeliveredPrice=50, listingType="buy_it_now", bestOfferEnabled=False,
        bidCount=None, auctionEndAt=None, imageUrl=None, sponsored=False, extractedAt=datetime.now(timezone.utc),
    )
    prices = PriceBundle(
        actualListing=50, ebayNewBin=_unavailable(), ebayUsedBin=_unavailable(),
        ebayNewSold=_unavailable(), ebayUsedSold=_unavailable(), amazonUkNew=_unavailable(),
    )
    return ScoredListing(
        rank=1, listing=listing, identity=Identity(brand=None, model=None, mpn=None, category=None, exactSkuConfidence=None),
        prices=prices, dealScore=deal_score, classification=classification, confidenceScore=50, confidenceBand="medium",
        decision="WATCH", flipScore=None, buildValueScore=None, inventoryAwareness=None, riskFlags=[],
        offerStrategy=None, reasoningSummary=None,
    )


@pytest.fixture(autouse=True)
def _isolate_scrapes_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "SCRAPES_DIR", tmp_path)
    return tmp_path


class TestScreenedJson:
    def test_writes_valid_json_sorted_by_score_desc(self, tmp_path):
        results = [_scored_listing("1", "OK_DEAL", 7.5), _scored_listing("2", "SUPER_GEM", 9.5)]
        path = evidence.write_screened_json("run1", "search1", "AM4 CPU", "https://example.com", None, results, 1)
        data = json.loads(open(path, encoding="utf-8").read())
        assert data["resultCount"] == 2
        assert data["results"][0]["dealScore"] == 9.5  # highest score first


class TestLatestGems:
    def test_only_super_gem_and_gem_are_persisted(self, tmp_path):
        results = [_scored_listing("1", "OK_DEAL", 7.5), _scored_listing("2", "SUPER_GEM", 9.5)]
        path = evidence.update_latest_gems(results)
        data = json.loads(open(path, encoding="utf-8").read())
        assert len(data) == 1
        assert data[0]["listing"]["listingId"] == "2"

    def test_repeat_sighting_updates_in_place_not_duplicated(self, tmp_path):
        evidence.update_latest_gems([_scored_listing("1", "GEM", 8.0)])
        evidence.update_latest_gems([_scored_listing("1", "GEM", 8.5)])
        data = json.loads((tmp_path / "latest_gems.json").read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["dealScore"] == 8.5


class TestRetentionCleanup:
    def test_deletes_files_older_than_window(self, tmp_path):
        old_file = tmp_path / "2020-01-01_00-00-00_old_search.pdf"
        old_file.write_text("x")
        old_time = time.time() - 48 * 3600
        import os
        os.utime(old_file, (old_time, old_time))

        removed = evidence.cleanup_old_artifacts(24, set(), set())
        assert removed == 1
        assert not old_file.exists()

    def test_never_deletes_latest_gems_json(self, tmp_path):
        gems_file = tmp_path / "latest_gems.json"
        gems_file.write_text("[]")
        old_time = time.time() - 48 * 3600
        import os
        os.utime(gems_file, (old_time, old_time))

        evidence.cleanup_old_artifacts(24, set(), set())
        assert gems_file.exists()

    def test_never_deletes_purchased_listing_evidence(self, tmp_path):
        purchased_file = tmp_path / "2020-01-01_00-00-00_AM4_CPU_SCREENED.json"
        purchased_file.write_text("{}")
        old_time = time.time() - 48 * 3600
        import os
        os.utime(purchased_file, (old_time, old_time))
        # This file doesn't embed a listing ID by name in this fixture, so
        # verify the mechanism directly: a file whose name contains a
        # preserved ID survives even though it's past the retention window.
        tagged_file = tmp_path / "2020-01-01_00-00-01_111222333_evidence.pdf"
        tagged_file.write_text("x")
        os.utime(tagged_file, (old_time, old_time))

        removed = evidence.cleanup_old_artifacts(24, {"111222333"}, set())
        assert tagged_file.exists()
        assert not purchased_file.exists()
        assert removed == 1

    def test_recent_files_are_kept(self, tmp_path):
        recent_file = tmp_path / "recent_search.pdf"
        recent_file.write_text("x")
        removed = evidence.cleanup_old_artifacts(24, set(), set())
        assert removed == 0
        assert recent_file.exists()
