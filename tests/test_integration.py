# tests/test_integration.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.core.database import init_db, engine
from sqlmodel import Session, SQLModel
import os


def get_test_pdf_content():
    """Get a minimal valid PDF content for testing"""
    test_pdf_path = os.path.join(
        os.path.dirname(__file__), "test_files", "test_program_plan.pdf"
    )
    with open(test_pdf_path, "rb") as f:
        return f.read()


@pytest.fixture(autouse=True)
def setup_database():
    """Setup a fresh database for each test"""
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def sample_pdf_message():
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456789",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "15556078886",
                                "phone_number_id": "123456789",
                            },
                            "contacts": [
                                {"profile": {"name": "Test User"}, "wa_id": "123456789"}
                            ],
                            "messages": [
                                {
                                    "from": "123456789",
                                    "type": "document",
                                    "document": {
                                        "filename": "test.pdf",
                                        "mime_type": "application/pdf",
                                        "id": "test_doc_id",
                                    },
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


@pytest.mark.asyncio
async def test_complete_flow(
    sample_pdf_message, setup_database, client, twilio_webhook_media_form_data
):
    """Test the complete flow from PDF upload to question answering"""
    # Mock PDF download and processing
    with patch(
        "app.core.pdf_processor.PDFProcessor.download_pdf_from_whatsapp"
    ) as mock_download:
        mock_download.return_value = get_test_pdf_content()

        # Mock LangChain processing
        with patch(
            "app.services.langchain_service.LLMService.process_document"
        ) as mock_process:
            # Mock Twilio send_message
            with patch(
                "app.core.twilio_whatsapp_client.TwilioWhatsAppClient.send_message"
            ) as mock_send:
                mock_send.return_value = {"sid": "test_sid"}

                # Create form data for Twilio webhook with PDF
                form_data = twilio_webhook_media_form_data(
                    media_content_type="application/pdf",
                    media_url="https://api.twilio.com/media/test.pdf",
                )

                # Send PDF using form data
                response = client.post("/webhook", data=form_data)
                assert response.status_code == 200

                # Verify mocks were called - expect download to be called twice
                assert mock_download.call_count == 2
                mock_process.assert_called_once()
                assert mock_send.call_count == 2
