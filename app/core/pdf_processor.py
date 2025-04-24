# app/core/pdf_processor.py

from pathlib import Path
from typing import List
import pypdf
import fitz
import io
from fastapi import UploadFile
from fastapi import HTTPException
import logging
from app.core.twilio_whatsapp_client import TwilioWhatsAppClient


class PDFProcessor:
    """Processes uploaded PDF files"""

    def __init__(self, wa_client: TwilioWhatsAppClient, upload_dir: str = "uploads"):
        """Initialize the PDFProcessor with an upload directory and WhatsApp client"""
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)
        self.wa_client = wa_client

    async def save_pdf(self, file: UploadFile) -> Path:
        """Save uploaded PDF file"""
        if not file.filename:
            raise ValueError("File must have a filename")

        file_path = self.upload_dir / file.filename
        content = await file.read()
        file_path.write_bytes(content)
        return file_path

    def extract_text(self, file_path: Path) -> str:
        """Extract text from PDF using pypdf"""
        text = ""
        try:
            with open(file_path, "rb") as file:
                # Use pypdf reader
                reader = pypdf.PdfReader(file)
                num_pages = len(reader.pages)
                for i in range(num_pages):
                    page = reader.pages[i]
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text
        except Exception as e:
            logging.error(f"Error extracting text from {file_path} using pypdf: {e}")
            raise
        return text

    def get_pages(self, pdf_path: Path) -> List[fitz.Page]:
        """Get all pages from a PDF file"""
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file {pdf_path} does not exist")

        doc = fitz.open(pdf_path)
        return list(doc)

    def get_first_page_image(self, file_path: Path) -> Path:
        """Get a base64 encoded image of the first page"""
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"File {file_path} does not exist")

            # Get file extension
            ext = file_path.suffix.lower()

            # Handle different file types
            if ext == ".pdf":
                # Open PDF and convert first page to image using PyMuPDF
                pdf_document = fitz.open(str(file_path))
                if len(pdf_document) == 0:
                    pdf_document.close()
                    raise ValueError("PDF document is empty")

                first_page = pdf_document[0]
                pix = first_page.get_pixmap()

                # Save image to file
                image_path = self.upload_dir / f"{file_path.stem}_page1.png"
                pix.save(str(image_path))
                pdf_document.close()

                return image_path

            elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif"]:
                # For image files, just return the path
                return file_path
            else:
                raise ValueError(f"Unsupported file type {ext}")

        except Exception as e:
            logging.error(f"Error processing file {file_path}: {e}")
            raise Exception(f"Error processing file: {str(e)}") from e

    async def download_pdf_from_whatsapp(self, document: dict) -> bytes:
        """Downloads the PDF using the media link provided by Twilio."""
        media_link = document["link"]
        pdf_bytes, real_name = await self.wa_client.download_media(media_link)
        document["filename"] = real_name
        return pdf_bytes

    def extract_text_from_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes using pypdf"""
        text = ""
        try:
            pdf_stream = io.BytesIO(pdf_bytes)
            reader = pypdf.PdfReader(pdf_stream)
            num_pages = len(reader.pages)
            for i in range(num_pages):
                page = reader.pages[i]
                page_text = page.extract_text()
                if page_text:
                    text += page_text
        except Exception as e:
            logging.error(
                f"Error extracting text from PDF bytes using pypdf: {e}", exc_info=True
            )
            raise
        return text
