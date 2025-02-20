# test_api.py

import pytest
from fastapi.testclient import TestClient
from app.main import app

# Initialize the test client
client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Whatsapp PDF Assistant"} 