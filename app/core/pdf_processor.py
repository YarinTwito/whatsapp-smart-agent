from pathlib import Path
from typing import List
import pypdf
import fitz  # type: ignore  # PyMuPDF
import io
import base64
from PIL import Image
from fastapi import UploadFile


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

    def get_pages(self, file_path: Path) -> List[str]:
        """Get list of pages from PDF"""
        with open(file_path, "rb") as file:
            pdf = pypdf.PdfReader(file)
            return [page.extract_text() for page in pdf.pages]

    def get_first_page_image(self, file_path: Path) -> str:
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
                img_data = pix.tobytes("png")

                # Convert to PIL Image
                image = Image.open(io.BytesIO(img_data))
                pdf_document.close()
            elif ext in [".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".gif"]:
                # Open image file directly
                image = Image.open(file_path)
            else:
                raise Exception(f"Unsupported file type {ext}")

            # Convert image to base64
            buffer = io.BytesIO()
            image.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

        except Exception as e:
            raise Exception(f"Error processing file: {str(e)}")
