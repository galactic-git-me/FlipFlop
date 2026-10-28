from app.services.catalogue_marketing_copy import source_fact_copy
import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_cached_hover_does_not_wait_for_enrichment_lock():
    from app.services.catalogue_marketing_copy import cache_source_guide
    row = SimpleNamespace(source_hash="current")
    db = SimpleNamespace(execute=AsyncMock())
    with patch("app.services.catalogue_marketing_copy._load_cached", AsyncMock(return_value=row)):
        assert await cache_source_guide(db, {"source_hash": "current"}) is row
    db.execute.assert_not_called()


def test_guide_uses_recorded_facts_and_explains_missing_specs():
    copy = source_fact_copy({"title": "Example CPU", "specifications": {"cores": 8}, "parsed": {}})
    assert copy["headline"] == "Example CPU"
    assert "not yet been captured" in copy["summary"]
    assert copy["key_details"] == [{"label": "Cores", "value": "8"}]
    assert copy["benefits"] == []


def test_upgrade_compares_only_recorded_baseline_differences():
    copy = source_fact_copy({"title": "64GB memory", "specifications": {"capacity": "64GB"},
        "upgrade_context": {"baseline_model": "32GB memory", "baseline_specifications": {"capacity": "32GB"}}})
    assert "32GB memory" in copy["summary"]
    assert copy["benefits"] == [{"title": "Capacity", "description": "64GB instead of 32GB."}]
    assert "faster" not in str(copy)


def test_unverified_alternative_never_claims_improvement():
    copy = source_fact_copy({"title": "Alternative GPU", "upgrade_context": {"baseline_model": "Original GPU"}})
    assert "performance improvement has not been verified" in copy["summary"]
    assert copy["benefits"] == []


def test_source_html_is_rendered_as_plain_text():
    copy = source_fact_copy({"title": "Product", "vendor_description": "<b>Vendor &amp; facts</b>"})
    assert copy["summary"] == "Vendor & facts"
