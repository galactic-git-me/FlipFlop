from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.assets_admin import CaseMeshyGenerate, _owner_approved_case_images
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.routes.cases import CaseReferenceApproval, _priority_case_filter, _priority_source_filter


def _image(index: int) -> dict[str, str]:
    return {"url": f"https://images.example.test/case-{index}.jpg", "source": "manufacturer"}


def test_reference_approval_requires_exactly_four_images() -> None:
    with pytest.raises(ValidationError):
        CaseReferenceApproval(selected_images=[_image(1), _image(2), _image(3)])


def test_generation_requires_the_saved_four_images_in_saved_order() -> None:
    images = [_image(index) for index in range(1, 5)]
    case = SimpleNamespace(sourcing_3d_evidence={
        "stages": {"product_images": {"approved_selection": {"status": "approved", "images": images}}}
    })
    urls = [image["url"] for image in images]
    assert _owner_approved_case_images(case, urls) == urls
    with pytest.raises(HTTPException, match="approved order"):
        _owner_approved_case_images(case, list(reversed(urls)))


def test_generation_contract_requires_four_images() -> None:
    with pytest.raises(ValidationError):
        CaseMeshyGenerate(image_urls=["https://images.example.test/one.jpg"])


def test_overclockers_priority_filter_includes_uk_suffix_variants() -> None:
    expression = _priority_source_filter("Overclockers")
    sql = str(expression.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "like" in sql
    assert "%overclockers%" in sql


def test_campaign_priority_filter_remains_unfiltered_by_source() -> None:
    assert _priority_source_filter(None) is None


def test_frozen_campaign_also_includes_unranked_overclockers_cases() -> None:
    sql = str(_priority_case_filter(None, True).compile(compile_kwargs={"literal_binds": True})).lower()
    assert "priority_3d_rank is not null" in sql
    assert "%overclockers%" in sql
    assert " or " in sql


def test_scored_listing_model_maps_all_market_classification_columns() -> None:
    expected = {
        "market_lower_price", "market_median_price", "market_upper_price",
        "pct_offset", "recommendation",
    }
    assert expected.issubset(GemRadarScoredListing.__table__.columns.keys())
