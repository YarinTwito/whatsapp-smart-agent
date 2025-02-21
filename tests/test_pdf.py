"""Test PDF processor functionality."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.pdf_processor import PDFProcessor


client = TestClient(app)


def test_pdf_upload_invalid_file():
    response = client.post(
        "/upload-pdf", files={"file": ("test.txt", b"test content", "text/plain")}
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_get_first_page_image(tmp_path):
    processor = PDFProcessor(upload_dir=str(tmp_path))

    with pytest.raises(Exception) as exc_info:
        processor.get_first_page_image(tmp_path / "nonexistent.pdf")
    assert "does not exist" in str(exc_info.value)

    invalid_file = tmp_path / "test.txt"
    invalid_file.write_text("test content")
    with pytest.raises(Exception) as exc_info:
        processor.get_first_page_image(invalid_file)
    assert "Unsupported file type" in str(exc_info.value)
