# tests/test_structure.py

import pytest
import importlib
from app import create_app

def test_imports():
    """Test that all necessary modules can be imported"""
    # Test core imports
    assert importlib.import_module("app.core.database")
    assert importlib.import_module("app.core.pdf_processor")
    assert importlib.import_module("app.core.whatsapp_client")
    
    # Test data schema imports
    assert importlib.import_module("app.data_schemas.pdf_document")
    assert importlib.import_module("app.data_schemas.processed_message")
    
    # Test that models are accessible through __init__
    from app.data_schemas import PDFDocument, ProcessedMessage
    assert PDFDocument
    assert ProcessedMessage 