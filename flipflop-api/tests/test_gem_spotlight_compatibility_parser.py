import pytest

from app.api.gem_radar import _parse_gem_compatibility_response


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
