# tests/test_pdf.py

"""Test PDF processor functionality."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.pdf_processor import PDFProcessor
import io
from PIL import Image
from fastapi import UploadFile
import fitz  # PyMuPDF
from pathlib import Path
from unittest.mock import Mock, patch
from app.models import PDFDocument
from fastapi import HTTPException
from unittest.mock import AsyncMock
import pypdf


client = TestClient(app)


def test_pdf_upload_invalid_file():
    response = client.post(
        "/upload-pdf", files={"file": ("test.txt", b"test content", "text/plain")}
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_get_first_page_image(tmp_path, sample_pdf):
    processor = PDFProcessor(upload_dir=str(tmp_path))
    
    # Test with non-existent file
    with pytest.raises(Exception) as exc_info:
        processor.get_first_page_image(tmp_path / "nonexistent.pdf")
    assert "does not exist" in str(exc_info.value)
    
    # Test with invalid file
    invalid_file = tmp_path / "test.txt"
    invalid_file.write_text("test content")
    with pytest.raises(Exception) as exc_info:
        processor.get_first_page_image(invalid_file)
    assert "Unsupported file type" in str(exc_info.value)
    
    # Test with valid PDF
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(sample_pdf)
    
    # Get first page image
    image_path = processor.get_first_page_image(pdf_path)
    assert Path(image_path).exists()
    
    # Verify it's a valid image
    img = Image.open(image_path)
    assert img.format in ['JPEG', 'PNG']


def test_extract_text(tmp_path, sample_pdf):
    processor = PDFProcessor(upload_dir=str(tmp_path))
    
    # Test with invalid file
    invalid_file = tmp_path / "test.txt"
    invalid_file.write_text("test content")
    with pytest.raises(Exception):
        processor.extract_text(invalid_file)
    
    # Test with valid PDF
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(sample_pdf)
    
    text = processor.extract_text(pdf_path)
    assert "Test PDF Content" in text


def test_get_pages(tmp_path, sample_pdf):
    processor = PDFProcessor(upload_dir=str(tmp_path))
    
    # Test with non-existent file
    with pytest.raises(Exception):
        processor.get_pages(tmp_path / "nonexistent.pdf")
    
    # Test with valid PDF
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(sample_pdf)
    
    pages = processor.get_pages(pdf_path)
    assert len(pages) == 1  # Our sample PDF has 1 page
    assert isinstance(pages[0], fitz.Page)


@pytest.mark.asyncio
async def test_save_pdf(tmp_path, pdf_upload_file):
    processor = PDFProcessor(upload_dir=str(tmp_path))
    
    saved_path = await processor.save_pdf(pdf_upload_file)
    assert saved_path.exists()
    
    # Verify it's a valid PDF
    doc = fitz.open(saved_path)
    assert doc.page_count == 1
    text = doc[0].get_text()
    assert "Test PDF Content" in text


def test_extract_text_from_bytes_empty():
    """Test handling of empty PDF content"""
    processor = PDFProcessor()
    with pytest.raises(Exception):
        processor.extract_text_from_bytes(b"")


@pytest.mark.asyncio
async def test_extract_text_from_bytes_invalid():
    """Test handling of invalid PDF format"""
    processor = PDFProcessor()
    with pytest.raises(Exception):
        processor.extract_text_from_bytes(b"not a pdf content")


@pytest.mark.asyncio
async def test_download_pdf_error():
    """Test error handling during PDF download"""
    processor = PDFProcessor()
    with pytest.raises(HTTPException):
        await processor.download_pdf_from_whatsapp("invalid_file_id")


@pytest.mark.asyncio
async def test_get_pdf_content_large():
    """Test processing of large PDF content"""
    processor = PDFProcessor()
    
    # Create a real PDF in memory
    pdf_bytes = io.BytesIO()
    pdf_writer = pypdf.PdfWriter()
    # Add a large page with some text
    page = pdf_writer.add_blank_page(width=612, height=792)
    pdf_writer.write(pdf_bytes)
    large_content = pdf_bytes.getvalue()
    
    with patch('httpx.AsyncClient.get') as mock_get:
        # Create two mock responses for the two API calls
        mock_url_response = AsyncMock()
        mock_url_response.status_code = 200
        mock_url_response.json = AsyncMock(return_value={"url": "http://test.url"})

        mock_content_response = AsyncMock()
        mock_content_response.status_code = 200
        mock_content_response.content = large_content  # Use real PDF content

        # Set up the mock to return different responses for each call
        mock_get.side_effect = [mock_url_response, mock_content_response]
        
        result = await processor.get_pdf_content({"id": "test_id"})
        assert result is not None


@pytest.mark.asyncio
async def test_extract_text_from_bytes_large():
    """Test extracting text from large PDF bytes"""
    processor = PDFProcessor()
    # Create a sample PDF in memory
    with io.BytesIO() as pdf_buffer:
        pdf_writer = pypdf.PdfWriter()
        page = pdf_writer.add_blank_page(width=72, height=72)
        pdf_writer.write(pdf_buffer)
        pdf_bytes = pdf_buffer.getvalue()
        
        text = processor.extract_text_from_bytes(pdf_bytes)
        assert text is not None


@pytest.mark.asyncio
async def test_download_pdf_success():
    """Test successful PDF download"""
    processor = PDFProcessor()
    with patch('httpx.AsyncClient.get') as mock_get:
        mock_url_response = AsyncMock()
        mock_url_response.status_code = 200
        mock_url_response.json = AsyncMock(return_value={"url": "http://test.url"})
        
        mock_content_response = AsyncMock()
        mock_content_response.status_code = 200
        mock_content_response.content = b"PDF content"
        
        mock_get.side_effect = [mock_url_response, mock_content_response]
        
        result = await processor.download_pdf_from_whatsapp("test_id")
        assert result == b"PDF content"
