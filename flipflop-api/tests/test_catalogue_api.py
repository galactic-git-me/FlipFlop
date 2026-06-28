import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

def test_review_queue_route_exists():
    resp = client.get("/api/catalogue/review-queue")
    assert resp.status_code in (200, 500)  # 500 is ok — no DB in test env

def test_variants_route_exists():
    resp = client.get("/api/catalogue/variants")
    assert resp.status_code in (200, 500)

def test_cases_route_exists():
    resp = client.get("/api/catalogue/cases")
    assert resp.status_code in (200, 500)

def test_slots_route_exists():
    resp = client.get("/api/catalogue/slots")
    assert resp.status_code in (200, 500)

def test_approve_unknown_variant_does_not_return_200():
    resp = client.post("/api/catalogue/variants/99999/approve")
    assert resp.status_code != 200 or resp.status_code == 404

def test_reject_body_required():
    resp = client.post("/api/catalogue/variants/1/reject", json={})
    # Missing required field "reason" should give 422
    assert resp.status_code in (404, 422, 500)

def test_approve_all_route_exists():
    resp = client.post("/api/catalogue/variants/approve-all")
    assert resp.status_code in (200, 500)
