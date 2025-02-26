# tests/test_integration.py

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from app.core.database import init_db, engine
from sqlmodel import Session, SQLModel
import os

def get_test_pdf_content():
    """Get a minimal valid PDF content for testing"""
    test_pdf_path = os.path.join(os.path.dirname(__file__), 'test_files', 'test_program_plan.pdf')
    with open(test_pdf_path, 'rb') as f:
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
                        "type": "document",
                        "document": {
                            "filename": "test.pdf",
                            "mime_type": "application/pdf",
                            "id": "test_doc_id"
                        }
                    }]
                },
                "field": "messages"
            }]
        }]
    }

@pytest.mark.asyncio
async def test_complete_flow(sample_pdf_message, setup_database, client):
    """Test the complete flow from PDF upload to question answering"""
    # Mock PDF download and processing
    with patch('app.core.pdf_processor.PDFProcessor.download_pdf_from_whatsapp') as mock_download:
        mock_download.return_value = get_test_pdf_content()
        
        # Mock LangChain processing
        with patch('app.services.langchain_service.LLMService.process_document') as mock_process:
            # Mock WhatsApp send_message
            with patch('app.core.whatsapp_client.WhatsAppClient.send_message') as mock_send:
                mock_send.return_value = {"success": True}
                
                # Send PDF
                response = client.post("/webhook", json=sample_pdf_message)
                assert response.status_code == 200

                # Verify all mocks were called
                mock_download.assert_called_once()
                mock_process.assert_called_once()
                assert mock_send.call_count == 2
