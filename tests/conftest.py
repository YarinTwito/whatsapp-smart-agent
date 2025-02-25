# tests/conftest.py

import pytest
from dotenv import load_dotenv
import os
from reportlab.pdfgen import canvas
from io import BytesIO
from fastapi import UploadFile
import warnings

@pytest.fixture(autouse=True)
def load_test_env():
    """Load test environment variables for all tests"""
    load_dotenv("tests/test.env") 

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