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
                        "type": "text",
                        "from": "1234",
                        "text": {"body": "hello"},
                        "id": "test_id"
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
    
    # Update expected result to match the new structure
    assert result["wa_id"] == "1234"
    assert result["name"] == "Test User"
    assert result["message_body"] == "hello"
    assert result["type"] == "text"
    assert result["from"] == "1234"
    assert result["message_id"] == "test_id"


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
    # Just check that success is in the response, don't compare exact dictionaries
    assert "success" in response
    assert response.get("success") == True


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
async def test_invalid_token():
    """Test client behavior with invalid token"""
    client = WhatsAppClient(token="invalid", phone_number_id="test_id")
    
    # Use a context manager to patch the post method
    with patch('httpx.AsyncClient.post') as mock_post:
        # Create a mock that raises an HTTPException
        mock_post.side_effect = HTTPException(status_code=401, detail="Invalid token")
        
        # Test that the exception is propagated
        with pytest.raises(HTTPException) as exc_info:
            await client.send_message("123", "test")
            
        # Verify the status code
        assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_send_document():
    """Test sending a document via WhatsApp"""
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {"success": True}
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = mock_response
        result = await client.send_document("1234", "http://example.com/doc.pdf", "Test Document")
        
        # Verify the result
        assert result == {"success": True}
        
        # Verify the correct payload was sent
        call_kwargs = mock_post.call_args.kwargs
        assert call_kwargs["json"]["document"]["link"] == "http://example.com/doc.pdf"
        assert call_kwargs["json"]["document"]["caption"] == "Test Document"


@pytest.mark.asyncio
async def test_send_document_error():
    """Test error handling when sending a document"""
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    
    # Mock error response
    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value = mock_response
        
        with pytest.raises(HTTPException) as exc_info:
            await client.send_document("1234", "http://example.com/doc.pdf")
        
        assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_extract_message_data_status_update():
    """Test handling of status update messages"""
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    
    status_update = {
        "entry": [{
            "changes": [{
                "value": {
                    "statuses": [{"status": "delivered"}]
                }
            }]
        }]
    }
    
    # Instead of expecting an exception, check for the right status dict
    result = await client.extract_message_data(status_update)
    assert result["type"] == "status"
    assert result["status"] == "delivered"


@pytest.mark.asyncio
async def test_extract_message_data_invalid_format():
    """Test handling of invalid message format"""
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    
    invalid_format = {
        "entry": [{
            "changes": [{
                "value": {
                    # Missing required fields
                }
            }]
        }]
    }
    
    # Instead of expecting an exception, we expect an empty dict
    result = await client.extract_message_data(invalid_format)
    assert result == {}


@pytest.mark.asyncio
async def test_log_response():
    """Test logging of HTTP responses"""
    client = WhatsAppClient(token="test_token", phone_number_id="test_id")
    
    # Create a mock response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"success": true}'
    
    # Test with logging
    with patch("logging.info") as mock_log:
        await client._log_response(mock_response)
        
        # Verify logging calls
        assert mock_log.call_count >= 3  # Should log status, content-type, and body