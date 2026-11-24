from pathlib import Path


def test_apply_script_is_explicitly_conservative():
    source = Path("scripts/apply_identity_proposals.py").read_text()
    assert "p.method = 'exact_identifier'" in source
    assert "p.confidence >= 0.95" in source
    assert "s.cpk IS NULL" in source
