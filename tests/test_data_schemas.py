# tests/test_data_schemas.py

import pytest
from sqlmodel import Session, SQLModel
from app.data_schemas import PDFDocument, ProcessedMessage
from datetime import datetime

def test_pdf_document_creation():
    """Test PDFDocument schema creation and fields"""
    pdf_doc = PDFDocument(
        filename="test.pdf",
        content="Test content",
        user_id="123",
        whatsapp_file_id="456"
    )
    
    # Verify required fields
    assert pdf_doc.filename == "test.pdf"
    assert pdf_doc.content == "Test content"
    assert pdf_doc.user_id == "123"
    
    # Verify default values
    assert pdf_doc.processed == False
    assert isinstance(pdf_doc.upload_date, datetime)
    assert pdf_doc.id is None  # Should be None until added to database

def test_processed_message_creation():
    """Test ProcessedMessage schema creation and fields"""
    message = ProcessedMessage(
        message_id="msg_123",
        timestamp="1234567890"
    )
    
    # Verify required fields
    assert message.message_id == "msg_123"
    assert message.timestamp == "1234567890"
    
    # Verify default values
    assert isinstance(message.processed_at, datetime)
    assert message.id is None  # Should be None until added to database

def test_model_relationships():
    """Test that models are properly defined as SQLModel tables"""
    assert PDFDocument.__tablename__ == "pdfdocument"
    assert ProcessedMessage.__tablename__ == "processedmessage"
    
    # Verify they are SQLModel tables
    assert issubclass(PDFDocument, SQLModel)
    assert issubclass(ProcessedMessage, SQLModel) 