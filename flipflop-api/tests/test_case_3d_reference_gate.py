from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.background import BackgroundTasks

from app.api.assets_admin import CaseMeshyGenerate, _owner_approved_case_images
from app.models.gem_radar_scored_listing import GemRadarScoredListing
from app.routes.cases import CaseReferenceApproval, _priority_case_filter, _priority_source_filter, capture_3d_overclockers_gallery, router
from app.workers.overclockers_gallery import _gallery_cache_is_fresh


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


def test_overclockers_gallery_cache_expires_after_one_month() -> None:
    now = datetime(2026, 10, 11, 12, 0, 0)
    fresh = {"overclockers_gallery": ["https://img.example.test/case.jpg"], "overclockers_gallery_cached_at": (now - timedelta(days=29)).isoformat()}
    expired = {"overclockers_gallery": ["https://img.example.test/case.jpg"], "overclockers_gallery_cached_at": (now - timedelta(days=31)).isoformat()}

    assert _gallery_cache_is_fresh(fresh, now)
    assert not _gallery_cache_is_fresh(expired, now)


def test_overclockers_gallery_has_one_post_route() -> None:
    routes = [
        route for route in router.routes
        if getattr(route, "path", None) == "/cases/{case_id}/3d-overclockers-gallery"
        and "POST" in getattr(route, "methods", set())
    ]

    assert len(routes) == 1


@pytest.mark.asyncio
async def test_overclockers_gallery_post_queues_refresh_without_scraping() -> None:
    case = SimpleNamespace(id=340, sourcing_3d_evidence={})

    class Result:
        def scalar_one_or_none(self):
            return case

    class Session:
        committed = False

        async def execute(self, _statement):
            return Result()

        async def commit(self):
            self.committed = True

    background_tasks = BackgroundTasks()
    session = Session()
    result = await capture_3d_overclockers_gallery(340, background_tasks, None, session)

    assert result == {"ok": True, "queued": True, "status": "retrieving"}
    assert session.committed
    assert case.sourcing_3d_evidence["stages"]["product_images"]["overclockers_gallery_status"] == "retrieving"
    assert len(background_tasks.tasks) == 1


@pytest.mark.asyncio
async def test_overclockers_gallery_post_returns_fresh_cache_without_queueing() -> None:
    case = SimpleNamespace(id=340, sourcing_3d_evidence={
        "stages": {"product_images": {
            "overclockers_gallery": ["https://img.example.test/case.jpg"],
            "overclockers_gallery_cached_at": datetime.utcnow().isoformat(),
        }}
    })

    class Result:
        def scalar_one_or_none(self):
            return case

    class Session:
        async def execute(self, _statement):
            return Result()

    background_tasks = BackgroundTasks()
    result = await capture_3d_overclockers_gallery(340, background_tasks, None, Session())

    assert result == {"ok": True, "count": 1, "cached": True}
    assert not background_tasks.tasks


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
