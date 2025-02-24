# app/data_schemas/pdf_document.py

from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class PDFDocument(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    filename: str
    content: str = ""  # Empty initially, will be filled after processing
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    user_id: str  # WhatsApp user ID 
    whatsapp_file_id: Optional[str] = Field(default=None)
    processed: bool = Field(default=False)  # Track processing status 