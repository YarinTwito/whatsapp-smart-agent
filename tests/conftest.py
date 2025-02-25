# tests/conftest.py

import pytest
from dotenv import load_dotenv
import os
from reportlab.pdfgen import canvas
from io import BytesIO
from fastapi import UploadFile
import warnings
from fastapi.testclient import TestClient
import sys
import os

# Add project root to path to ensure imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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
    return UploadFile(
        filename="test.pdf",
        file=BytesIO(sample_pdf)
    ) 

@pytest.fixture(autouse=True)
def ignore_pypdf_warnings():
    """Ignore warnings from pypdf."""
    warnings.filterwarnings("ignore", category=UserWarning, module="pypdf")
    warnings.filterwarnings("ignore", category=Warning, module="pypdf") 