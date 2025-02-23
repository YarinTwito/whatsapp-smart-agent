from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class PDFDocument(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    filename: str
    content: str = ""  # Empty initially, will be filled after processing
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    user_id: str  # WhatsApp user ID 
    whatsapp_file_id: Optional[str] = Field(default=None)  # Make this optional
    processed: bool = Field(default=False)  # Track processing status 

class ProcessedMessage(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    message_id: str = Field(unique=True)  # WhatsApp message ID
    timestamp: str
    processed_at: datetime = Field(default_factory=datetime.utcnow) 