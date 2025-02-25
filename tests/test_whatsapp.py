# tests/test_whatsapp.py

import pytest
from app.core.whatsapp_client import WhatsAppClient
from fastapi import HTTPException
import httpx
import pytest
from unittest.mock import patch, MagicMock
from unittest.mock import patch, Mock
from app.core.whatsapp_client import WhatsAppClient
from requests.exceptions import RequestException
from unittest.mock import AsyncMock


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
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(return_value={"success": True})
    
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


@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_send_message_retry(mock_post):
    """Test message sending retry mechanism"""
    mock_error_response = AsyncMock()
    mock_error_response.status_code = 500
    mock_error_response.text = "Error"
    mock_error_response.json.return_value = {"error": "Failed"}
    
    mock_success_response = AsyncMock()
    mock_success_response.status_code = 200
    mock_success_response.text = "Success"
    mock_success_response.json.return_value = {"success": True}
    
    mock_post.side_effect = [mock_error_response, mock_success_response]
    
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    
    # First call should fail with 500
    with pytest.raises(HTTPException) as exc_info:
        await client.send_message("123", "test message")
    assert exc_info.value.status_code == 500
    
    # Second call should succeed
    response = await client.send_message("123", "test message")
    assert response == await mock_success_response.json()


@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_send_message_all_retries_fail(mock_post):
    """Test all retries failing"""
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Error"
    mock_post.return_value = mock_response
    
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    with pytest.raises(HTTPException) as exc_info:
        await client.send_message("123", "test message")
    
    assert exc_info.value.status_code == 500
    assert mock_post.call_count >= 1


@pytest.mark.asyncio
@patch('httpx.AsyncClient.post')
async def test_invalid_token(mock_post):
    """Test client behavior with invalid token"""
    # Create a mock response with 401 status
    mock_response = AsyncMock()
    mock_response.status_code = 401
    mock_response.text = "Invalid token"
    mock_response.headers = {"content-type": "application/json"}
    mock_response.json = AsyncMock(return_value={"error": "Invalid token"})
    mock_post.return_value = mock_response  # Return the response, don't raise exception
    
    client = WhatsAppClient(token="invalid", phone_number_id="test_id")
    with pytest.raises(HTTPException) as exc_info:
        await client.send_message("123", "test")
    assert exc_info.value.status_code == 401
    assert "Invalid token" in exc_info.value.detail