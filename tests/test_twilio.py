# tests/test_twilio.py

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
from app.core.twilio_whatsapp_client import TwilioWhatsAppClient
import httpx


def test_twilio_client_init():
    client = TwilioWhatsAppClient(
        sid="test_sid", token="test_token", from_number="1234567890"
    )
    assert client._client.username == "test_sid"
    assert client._client.password == "test_token"
    assert client.from_number == "whatsapp:+1234567890"

    # Test with number already in whatsapp format
    client2 = TwilioWhatsAppClient(
        sid="test_sid", token="test_token", from_number="whatsapp:+1234567890"
    )
    assert client2.from_number == "whatsapp:+1234567890"


@pytest.mark.asyncio
async def test_send_message():
    client = TwilioWhatsAppClient(
        sid="test_sid", token="test_token", from_number="1234567890"
    )

    # Mock the Twilio client's messages.create method
    mock_message = MagicMock()
    mock_message.sid = "test_message_sid"

    client._client.messages.create = MagicMock(return_value=mock_message)

    # Test sending a message
    result = await client.send_message("9876543210", "Hello, world!")

    # Verify the result
    assert result == {"sid": "test_message_sid"}

    # Verify the message creation call
    client._client.messages.create.assert_called_once_with(
        from_="whatsapp:+1234567890", to="whatsapp:+9876543210", body="Hello, world!"
    )


@pytest.mark.asyncio
async def test_download_media():
    client = TwilioWhatsAppClient(
        sid="test_sid", token="test_token", from_number="1234567890"
    )

    # Mock httpx client response
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"test content"
    mock_response.headers = {"content-disposition": "attachment; filename=test.pdf"}

    # Mock AsyncClient.get method
    mock_client = MagicMock()
    mock_client.__aenter__.return_value.get.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        content, filename = await client.download_media("https://example.com/test.pdf")

        # Verify the response
        assert content == b"test content"
        assert filename == "test.pdf"

        # Verify the get call
        mock_client.__aenter__.return_value.get.assert_called_once_with(
            "https://example.com/test.pdf", auth=("test_sid", "test_token")
        )


@pytest.mark.asyncio
async def test_download_media_no_filename():
    client = TwilioWhatsAppClient(
        sid="test_sid", token="test_token", from_number="1234567890"
    )

    # Mock httpx client response with no content-disposition header
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"test content"
    mock_response.headers = {}

    # Mock AsyncClient.get method
    mock_client = MagicMock()
    mock_client.__aenter__.return_value.get.return_value = mock_response

    with patch("httpx.AsyncClient", return_value=mock_client):
        content, filename = await client.download_media("https://example.com/test.pdf")

        # Verify the response
        assert content == b"test content"
        assert filename == "document.pdf"  # Default filename
