# test_api.py

"""Test API endpoints."""

from fastapi.testclient import TestClient
from app.main import app
import os

# Initialize the test client
client = TestClient(app)


class TestAPI:
    """Test API endpoints."""

    def test_health_check(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Whatsapp PDF Assistant"}


def test_webhook_verification():
    # Print the token to debug
    print("Using verify token:", os.getenv("VERIFY_TOKEN"))
    
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": os.getenv("VERIFY_TOKEN"),  # Use the actual token
        "hub.challenge": "1234"
    })
    assert response.status_code == 200
    assert response.text == "1234"

def test_webhook_verification_invalid_token():
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "1234"
    })
    assert response.status_code == 403

def test_webhook_verification_invalid_request():
    response = client.get("/webhook")
    assert response.status_code == 400

def test_webhook_message():
    # Test webhook with a sample message
    message = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "contacts": [{"wa_id": "123"}],
                    "messages": [{
                        "type": "text",
                        "text": {"body": "test"}
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    response = client.post("/webhook", json=message)
    assert response.status_code == 200

def test_webhook_message_invalid():
    invalid_message = {"object": "wrong_type"}
    response = client.post("/webhook", json=invalid_message)
    assert response.status_code == 200  # Should still return 200 for invalid messages

def test_webhook_status_update():
    status_message = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "statuses": [{"status": "delivered"}]
                },
                "field": "messages"
            }]
        }]
    }
    response = client.post("/webhook", json=status_message)
    assert response.status_code == 200
