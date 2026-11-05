from types import SimpleNamespace

from structlog.testing import capture_logs

from app.gem_radar.cpk_extractor import _parse_extraction_output


def test_parse_extraction_json_with_surrounding_text():
    selected = SimpleNamespace(raw={}, usage={})
    parsed = _parse_extraction_output(
        'Result: {"category":"cpu","brand":"amd","model":"ryzen-7"} done',
        selected,
    )
    assert parsed == {"category": "cpu", "brand": "amd", "model": "ryzen-7"}


def test_parse_extraction_invalid_json_returns_none_with_metadata():
    selected = SimpleNamespace(
        raw={"done_reason": "length", "eval_count": 256},
        usage={"completion_tokens": 256},
    )
    with capture_logs() as events:
        assert _parse_extraction_output('{"category":"cpu" "brand":"amd"}', selected) is None
    event = next(event for event in events if event.get("event") == "cpk_extractor.json_parse_failed")
    assert event["completion_tokens"] == 256
    assert event["done_reason"] == "length"
    assert "category" not in event


def test_parse_extraction_rejects_non_object_json():
    selected = SimpleNamespace(raw={}, usage={})
    assert _parse_extraction_output('[{"category":"cpu"}]', selected) is None
