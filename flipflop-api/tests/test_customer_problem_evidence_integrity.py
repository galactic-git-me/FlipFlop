import hashlib
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import orders


def test_case_evidence_download_serves_only_checksum_verified_bytes(tmp_path, monkeypatch):
    root = tmp_path / "customer_problem_evidence"
    monkeypatch.setattr(orders, "_CUSTOMER_CASE_EVIDENCE_ROOT", root)
    relative_key = "41/evidence.pdf"
    path = root / relative_key
    path.parent.mkdir(parents=True)
    original = b"%PDF-1.7\nverified evidence\n"
    path.write_bytes(original)
    item = {
        "id": "evidence-1",
        "storage_key": relative_key,
        "filename": "proof.pdf",
        "content_type": "application/pdf",
        "sha256": hashlib.sha256(original).hexdigest(),
    }
    problem = SimpleNamespace(evidence_files=[item])

    response = orders._customer_case_evidence_response(problem, "evidence-1")
    assert response.body == original
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"

    path.write_bytes(b"%PDF-1.7\ntampered evidence\n")
    with pytest.raises(HTTPException) as error:
        orders._customer_case_evidence_response(problem, "evidence-1")
    assert error.value.status_code == 409
    assert "integrity check" in error.value.detail


def test_case_evidence_download_rejects_missing_integrity_metadata(tmp_path, monkeypatch):
    root = tmp_path / "customer_problem_evidence"
    monkeypatch.setattr(orders, "_CUSTOMER_CASE_EVIDENCE_ROOT", root)
    relative_key = "42/evidence.jpg"
    path = root / relative_key
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff\xd8\xffimage-data")
    problem = SimpleNamespace(evidence_files=[{
        "id": "evidence-2",
        "storage_key": relative_key,
        "filename": "photo.jpg",
        "content_type": "image/jpeg",
    }])

    with pytest.raises(HTTPException) as error:
        orders._customer_case_evidence_response(problem, "evidence-2")
    assert error.value.status_code == 409
    assert "no valid integrity record" in error.value.detail
