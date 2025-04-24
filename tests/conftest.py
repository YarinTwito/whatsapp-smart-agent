# tests/conftest.py

import pytest
from dotenv import load_dotenv
import os
from reportlab.pdfgen import canvas
from io import BytesIO
from fastapi import UploadFile
import warnings
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
from app.core.twilio_whatsapp_client import TwilioWhatsAppClient
import sys
import os

# Add project root to path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app


@pytest.fixture(autouse=True)
def load_test_env():
    """Load test environment variables for all tests"""
    load_dotenv("tests/test.env")


@pytest.fixture
def app():
    """Create application for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return TestClient(app)


@pytest.fixture
def sample_pdf():
    """Create a sample PDF file for testing"""
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    c.drawString(100, 750, "Test PDF Content")
    c.showPage()
    c.save()

    # Get the value from the buffer
    pdf_content = buffer.getvalue()
    buffer.close()

    return pdf_content


@pytest.fixture
def pdf_upload_file(sample_pdf):
    """Create a FastAPI UploadFile with a PDF"""
    return UploadFile(filename="test.pdf", file=BytesIO(sample_pdf))


@pytest.fixture(autouse=True)
def ignore_pypdf_warnings():
    """Ignore warnings from pypdf."""
    warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")
    warnings.filterwarnings("ignore", category=Warning, module="pypdf")


from unittest.mock import MagicMock
from app.core.database import get_db


@pytest.fixture
def setup_admin_key():
    """Set admin API key for testing specific admin endpoints"""
    old_key = os.environ.get("ADMIN_API_KEY")
    api_key = "admin_secret_key"
    os.environ["ADMIN_API_KEY"] = api_key
    yield api_key  # Yield the key for tests to use
    if old_key is not None:
        os.environ["ADMIN_API_KEY"] = old_key
    else:
        # Ensure the key is removed if it wasn't there before
        if "ADMIN_API_KEY" in os.environ:
            del os.environ["ADMIN_API_KEY"]


@pytest.fixture
def mock_db_session(client):
    """Fixture to mock the database session and handle dependency override."""
    mock_session = MagicMock()

    def override_get_db():
        try:
            yield mock_session
        finally:
            pass

    # Apply the dependency override
    client.app.dependency_overrides[get_db] = override_get_db

    yield mock_session  # Provide the mock session to the test

    # Clean up the override after the test finishes
    del client.app.dependency_overrides[get_db]


@pytest.fixture
def whatsapp_text_message_payload():
    """Generate a standard WhatsApp text message webhook payload."""

    def _create_payload(
        sender_id="123456789",
        text="test",
        message_id="test_message_id",
        account_id="123456789",
        phone_number_id="123456789",
        display_phone_number="15556078886",
        profile_name="Test User",
    ):
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": account_id,
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": display_phone_number,
                                    "phone_number_id": phone_number_id,
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": profile_name},
                                        "wa_id": sender_id,
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": sender_id,
                                        "text": {"body": text},
                                        "type": "text",
                                        "id": message_id,
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

    return _create_payload


@pytest.fixture
def twilio_webhook_form_data():
    """Generate Twilio webhook form data for testing."""

    def _create_form_data(
        from_number="+123456789",
        wa_id="123456789",
        body="test message",
        num_media="0",
        profile_name="Test User",
        message_sid="SM123456789",
    ):
        # Format with whatsapp: prefix
        from_whatsapp = f"whatsapp:{from_number.lstrip('+')}"

        form_data = {
            "From": from_whatsapp,
            "WaId": wa_id,
            "Body": body,
            "NumMedia": num_media,
            "ProfileName": profile_name,
            "MessageSid": message_sid,
        }

        return form_data

    return _create_form_data


@pytest.fixture
def twilio_webhook_media_form_data():
    """Generate Twilio webhook form data with media for testing."""

    def _create_media_form_data(
        from_number="+123456789",
        wa_id="123456789",
        media_url="https://api.twilio.com/2010-04-01/Accounts/ACXXXXXXX/Messages/MMXXXXXXX/Media/MEXXXXXXX",
        media_content_type="application/pdf",
        num_media="1",
        profile_name="Test User",
        message_sid="SM123456789",
    ):
        # Format with whatsapp: prefix
        from_whatsapp = f"whatsapp:{from_number.lstrip('+')}"

        form_data = {
            "From": from_whatsapp,
            "WaId": wa_id,
            "NumMedia": num_media,
            "MediaUrl0": media_url,
            "MediaContentType0": media_content_type,
            "ProfileName": profile_name,
            "MessageSid": message_sid,
        }

        return form_data

    return _create_media_form_data


@pytest.fixture
def mock_twilio_client():
    """Mock Twilio WhatsApp client for tests."""
    client = AsyncMock(spec=TwilioWhatsAppClient)
    client.download_media = AsyncMock(return_value=(b"test pdf content", "test.pdf"))
    client.send_message = AsyncMock(return_value={"sid": "test_message_sid"})
    return client
