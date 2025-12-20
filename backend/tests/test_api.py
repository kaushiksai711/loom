import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db.arango import db

client = TestClient(app)

def test_read_main():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Cognitive Loom API is running"}

def test_create_session():
    response = client.post(
        "/api/v1/session/create",
        json={"title": "Test Session", "goal": "Testing API"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Session"
    assert "_id" in data
    assert "_key" in data

def test_initiate_harvest():
    # First create a session to link to (though currently harvest doesn't validate session_id existence strictly in DB, it's good practice)
    session_res = client.post(
        "/api/v1/session/create",
        json={"title": "Harvest Session", "goal": "Harvesting"}
    )
    session_id = session_res.json()["_key"]

    response = client.post(
        "/api/v1/harvest/initiate",
        json={
            "highlight": "Test Highlight",
            "context": "Test Context",
            "source_url": "http://example.com",
            "session_id": session_id
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "seed_id" in data
