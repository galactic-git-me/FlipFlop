import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app, raise_server_exceptions=False)

def test_public_playbooks_route_exists():
    resp = client.get("/api/public/playbooks")
    assert resp.status_code == 200

def test_public_cases_route_exists():
    resp = client.get("/api/public/cases")
    assert resp.status_code == 200

def test_public_playbook_slots_route_exists():
    resp = client.get("/api/public/playbooks/1/slots")
    assert resp.status_code in (200, 404)

def test_public_playbook_slots_nonexistent_returns_not_200():
    resp = client.get("/api/public/playbooks/99999/slots")
    assert resp.status_code == 404


def test_budget_recommendation_validates_budget():
    resp = client.post("/api/public/recommendation", json={"purpose": "Great-value Gaming", "budget_gbp": 0})
    assert resp.status_code == 422
