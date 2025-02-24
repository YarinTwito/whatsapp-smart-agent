# tests/test_whatsapp.py

import pytest
from app.core.whatsapp_client import WhatsAppClient
from fastapi import HTTPException
import httpx
import pytest
from unittest.mock import patch, MagicMock

def test_whatsapp_client_init():
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    assert client.token == "test_token"
    assert client.phone_number_id == "test_id"
    assert "Bearer test_token" in client.headers["Authorization"]

def test_process_text_for_whatsapp():
    text = "Hello **world** 【test】"
    result = WhatsAppClient.process_text_for_whatsapp(text)
    assert result == "Hello *world*"  # Should remove 【test】 and convert **

def test_prepare_message_payload():
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    payload = client._prepare_message_payload("1234", "Hello")
    assert payload == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "1234",
        "type": "text",
        "text": {"preview_url": False, "body": "Hello"}
    }

def test_is_valid_message():
    # Test valid message
    valid_message = {
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
    assert WhatsAppClient.is_valid_message(valid_message) == True

    # Test invalid message
    invalid_message = {"object": "wrong_type"}
    assert WhatsAppClient.is_valid_message(invalid_message) == False

    # Test status update
    status_message = {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "value": {
                    "messaging_product": "whatsapp",
                    "statuses": [{"status": "sent"}]
                },
                "field": "messages"
            }]
        }]
    }
    assert WhatsAppClient.is_valid_message(status_message) == False

@pytest.mark.asyncio
async def test_send_message():
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    
    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"success": True}
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = mock_response
        result = await client.send_message("1234", "Hello")
        assert result == {"success": True}

@pytest.mark.asyncio
async def test_send_message_error():
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    
    # Mock error response
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.side_effect = httpx.TimeoutException("Timeout")
        
        with pytest.raises(HTTPException) as exc_info:
            await client.send_message("1234", "Hello")
        assert exc_info.value.status_code == 408

@pytest.mark.asyncio
async def test_extract_message_data():
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    
    valid_body = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "text": {"body": "hello"}
                    }],
                    "contacts": [{
                        "wa_id": "1234",
                        "profile": {"name": "Test User"}
                    }]
                }
            }]
        }]
    }
    
    result = await client.extract_message_data(valid_body)
    assert result == {
        "wa_id": "1234",
        "name": "Test User",
        "message_body": "hello"
    }