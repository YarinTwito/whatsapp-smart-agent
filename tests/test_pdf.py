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
