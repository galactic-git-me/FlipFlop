from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api.assets_admin import CaseMeshyGenerate, _owner_approved_case_images
from app.routes.cases import CaseReferenceApproval


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
