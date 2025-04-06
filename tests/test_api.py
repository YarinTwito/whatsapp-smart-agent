# test_api.py

"""Test API endpoints."""

from unittest.mock import patch
import pytest
import os

class TestAPI:
    """Test API endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


def test_read_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, Whatsapp PDF Assistant"}


def test_webhook_verification(client):
    # Print the token to debug
    print("Using verify token:", os.getenv("VERIFY_TOKEN"))

    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": os.getenv("VERIFY_TOKEN"),
        "hub.challenge": "1234"
    })
    assert response.status_code == 200
    assert response.text == "1234"

def test_webhook_verification_invalid_token(client):
    response = client.get("/webhook", params={
        "hub.mode": "subscribe",
        "hub.verify_token": "wrong_token",
        "hub.challenge": "1234"
    })
    assert response.status_code == 403

def test_webhook_verification_invalid_request(client):
    response = client.get("/webhook")
    assert response.status_code == 400

@patch('app.core.whatsapp_client.WhatsAppClient.send_message')
@patch('app.services.langchain_service.LLMService.get_answer')
def test_webhook_message(mock_get_answer, mock_send_message, client):
    # Configure the mocks
    mock_send_message.return_value = {"success": True}
    mock_get_answer.return_value = "This is a test answer"
    
    message = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123456789",
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {
                        "display_phone_number": "15556078886",
                        "phone_number_id": "123456789"
                    },
                    "contacts": [{
                        "profile": {"name": "Test User"},
                        "wa_id": "123456789"
                    }],
                    "messages": [{
                        "from": "123456789",
                        "text": {"body": "test"},
                        "type": "text",
                        "id": "test_message_id"
                    }]
                },
                "field": "messages"
            }]
        }]
    }
    response = client.post("/webhook", json=message)
    assert response.status_code == 200
    
    # Verify that send_message was called
    mock_send_message.assert_called_once()

def test_webhook_message_invalid(client):
    invalid_message = {"object": "wrong_type"}
    response = client.post("/webhook", json=invalid_message)
    assert response.status_code == 400

def test_webhook_status_update(client):
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
