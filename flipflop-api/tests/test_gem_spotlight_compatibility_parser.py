import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.gem_radar import _parse_gem_compatibility_response, _review_gem_spotlight_compatibility


def test_parses_json_only_response():
    assert _parse_gem_compatibility_response(
        '{"checks":[{"build":"best","pair":"cpu_motherboard","verdict":"compatible"}]}'
    )["checks"][0]["verdict"] == "compatible"


def test_parses_fenced_json_response():
    result = _parse_gem_compatibility_response(
        'Result follows:\n```json\n{"checks":[]}\n```\nDone.'
    )
    assert result == {"checks": []}


def test_normalizes_compact_llm_check_triples():
    result = _parse_gem_compatibility_response(
        '{"checks":[["best","cpu_motherboard","compatible"]]}'
    )
    assert result["checks"] == [{
        "build": "best", "pair": "cpu_motherboard", "verdict": "compatible"
    }]


def test_ignores_unrelated_braces_before_valid_response():
    result = _parse_gem_compatibility_response(
        'The example {} is not the result. {"checks":[]}'
    )
    assert result == {"checks": []}


@pytest.mark.parametrize("text", ["", "{\"checks\":[", "{\"other\":[]}"])
def test_rejects_missing_or_truncated_checks_json(text):
    with pytest.raises(ValueError, match="complete checks JSON"):
        _parse_gem_compatibility_response(text)


@pytest.mark.asyncio
async def test_captured_properties_keep_their_build_association():
    source_rows = [
        SimpleNamespace(listing_id=1, commercial_source_evidence={"url": "https://parts.test/cpu"}, observed_at=1, id=1),
        SimpleNamespace(listing_id=2, commercial_source_evidence={"url": "https://parts.test/board"}, observed_at=1, id=2),
    ]
    catalogue_rows = [
        SimpleNamespace(url="https://parts.test/cpu", raw_specs={"playbook_product_capture": {
            "status": "captured", "url": "https://parts.test/cpu", "product_properties": {"socket": "AM4"}}}),
        SimpleNamespace(url="https://parts.test/board", raw_specs={"playbook_product_capture": {
            "status": "captured", "url": "https://parts.test/board", "product_properties": {"socket": "AM4"}}}),
    ]
    db = SimpleNamespace(execute=AsyncMock(side_effect=[
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: source_rows)),
        SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: catalogue_rows)),
    ]))
    builds = {"best": {"title": "Best build", "gems": {
        "cpu": {"listing_id": 1, "title": "CPU"},
        "motherboard": {"listing_id": 2, "title": "Board"},
    }}}
    model_result = SimpleNamespace(text='{"checks":[["best","cpu_motherboard","compatible"]]}', model="qwen3:4b")
    with patch("app.services.model_selection_service.model_selection_service.complete", new=AsyncMock(return_value=model_result)) as complete, \
         patch("app.services.compatibility_llm_review.validate_compatibility_review", side_effect=lambda _offer, review: review):
        result = await _review_gem_spotlight_compatibility(db, builds)

    complete.assert_awaited_once()
    assert result["reviews"]["best"]["checks"][0]["pair"] == "cpu_motherboard"
