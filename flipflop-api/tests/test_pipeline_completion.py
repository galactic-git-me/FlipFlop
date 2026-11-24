"""Regression tests for the Sourcing card completion state."""

from app.gem_radar.pipeline_status import is_scan_complete


def _complete(**overrides: int) -> bool:
    values = {
        "active_submissions": 0,
        "queued_submissions": 0,
        "ingested_count": 1_850,
        "cpk_assigned_count": 1_814,
        "cpk_failed_count": 36,
        "market_priced_count": 1_487,
        "eligible_score_count": 719,
        "ineligible_score_count": 416,
    }
    values.update(overrides)
    return is_scan_complete(**values)


def test_scan_with_blank_scores_segment_is_not_complete() -> None:
    """The Intel CPU example has 352 market-priced listings still unscored."""
    assert not _complete()


def test_scan_is_complete_when_every_market_price_has_terminal_score() -> None:
    assert _complete(ineligible_score_count=768)


def test_cpk_failure_is_terminal_but_a_live_submission_is_not() -> None:
    assert not _complete(ineligible_score_count=768, active_submissions=1)
