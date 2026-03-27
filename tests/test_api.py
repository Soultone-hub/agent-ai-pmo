import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Agent IA PMO operationnel"}

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_list_documents_projet_inexistant():
    response = client.get("/api/documents/?project_id=00000000-0000-0000-0000-000000000000")
    assert response.status_code == 200
    assert "documents" in response.json()

def test_get_risks_projet_inexistant():
    response = client.get("/api/risks/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

def test_get_copil_projet_inexistant():
    response = client.get("/api/copil/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

def test_get_kpi_projet_inexistant():
    response = client.get("/api/kpi/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404

def test_chat_reset_projet_inexistant():
    response = client.delete("/api/chat/reset/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 200

def test_chat_history_projet_inexistant():
    response = client.get("/api/chat/history/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404