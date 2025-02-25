# app/core/pdf_processor.py

from pathlib import Path
from typing import List
import pypdf
import fitz
import io
import base64
from PIL import Image
from fastapi import UploadFile
import os
import httpx
from fastapi import HTTPException
import tempfile
import logging


class PDFProcessor:
    """Processes uploaded PDF files"""


    def __init__(self, upload_dir: str = "uploads"):
        """Initialize the PDFProcessor with an upload directory"""
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(exist_ok=True)


    async def save_pdf(self, file: UploadFile) -> Path:
        """Save uploaded PDF file"""
        if not file.filename:
            raise ValueError("File must have a filename")

        file_path = self.upload_dir / file.filename
        content = await file.read()
        file_path.write_bytes(content)
        return file_path


    def extract_text(self, file_path: Path) -> str:
        """Extract text from PDF"""
        with open(file_path, "rb") as file:
            pdf = pypdf.PdfReader(file)
            text = ""
            for page in pdf.pages:
                text += page.extract_text()
        return text


    def get_pages(self, pdf_path: Path) -> List[fitz.Page]:
        """Get all pages from a PDF file"""
        if not pdf_path.exists():
            raise Exception(f"PDF file {pdf_path} does not exist")
        
        doc = fitz.open(pdf_path)
        return [page for page in doc]  # Return actual Page objects


    def get_first_page_image(self, file_path: Path) -> Path:
        """Get a base64 encoded image of the first page"""
        try:
            if not file_path.exists():
                raise Exception(f"File {file_path} does not exist")

            # Get file extension
            ext = file_path.suffix.lower()

            # Handle different file types
            if ext == ".pdf":
                # Open PDF and convert first page to image using PyMuPDF
                pdf_document = fitz.open(str(file_path))
                if len(pdf_document) == 0:
                    raise Exception("PDF document is empty")

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
                raise Exception(f"Unsupported file type {ext}")

        except Exception as e:
            raise Exception(f"Error processing file: {str(e)}")


    async def get_pdf_content(self, document: dict) -> str:
        """Download and extract text from a WhatsApp PDF document"""
        try:
            print(f"Document data: {document}")
            print(f"Document type: {type(document)}")
            
            # Get document ID
            file_id = document.get("id")
            print(f"File ID: {file_id}")
            
            if not file_id:
                raise ValueError("No document ID provided")
            
            # Download PDF from WhatsApp servers
            pdf_data = await self.download_pdf_from_whatsapp(document)
            
            # Extract text
            text = self.extract_text_from_bytes(pdf_data)
            
            return text
        except Exception as e:
            print(f"Error processing PDF content: {str(e)}")
            raise


    async def download_pdf_from_whatsapp(self, document: dict) -> bytes:
        """Download a PDF file from WhatsApp using the Media API"""
        try:
            # Extract the document ID
            document_id = document.get("id")
            if not document_id:
                raise ValueError("Document ID is missing")
            
            # Construct the proper URL with the document ID
            url = f"https://graph.facebook.com/{os.getenv('VERSION')}/{document_id}"
            
            # Get WhatsApp token from environment
            token = os.getenv("WHATSAPP_TOKEN")
            if not token:
                raise ValueError("WhatsApp token is missing")
            
            headers = {
                "Authorization": f"Bearer {token}"
            }
            
            logging.info(f"Downloading document from: {url}")
            
            # First request to get the URL to download the media
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code != 200:
                    logging.error(f"Failed to get media URL: {response.text}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Failed to get media URL: {response.text}"
                    )
                
                # Parse the response to get the media URL
                media_data = response.json()
                if "url" not in media_data:
                    logging.error(f"Media URL not found in response: {media_data}")
                    raise ValueError("Media URL not found in API response")
                
                media_url = media_data["url"]
                
                # Second request to download the actual media file
                media_response = await client.get(media_url, headers=headers)
                
                if media_response.status_code != 200:
                    logging.error(f"Failed to download media: {media_response.text}")
                    raise HTTPException(
                        status_code=media_response.status_code,
                        detail=f"Failed to download media: {media_response.text}"
                    )
                
                # Return the binary content
                return media_response.content
        except Exception as e:
            logging.error(f"Error downloading PDF: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error downloading PDF: {str(e)}"
            )


    def extract_text_from_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes"""
        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as temp_file:
            temp_file.write(pdf_bytes)
            temp_file.flush()
            
            # Extract text using existing method
            return self.extract_text(temp_file.name)
