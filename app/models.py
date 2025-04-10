# app/models.py

from sqlmodel import SQLModel, Field
from datetime import datetime
from typing import Optional

class PDFDocument(SQLModel, table=True):
    """Model for storing PDF documents"""
    __table_args__ = {'extend_existing': True}
    
    id: int = Field(default=None, primary_key=True)
    filename: str
    content: str = ""  # Empty initially, will be filled after processing
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    user_id: str  # WhatsApp user ID 
    whatsapp_file_id: Optional[str] = Field(default=None)  # Make this optional
    processed: bool = Field(default=False)  # Track processing status 

class ProcessedMessage(SQLModel, table=True):
    """Model for tracking processed messages"""
    __table_args__ = {'extend_existing': True}
    
    id: int = Field(default=None, primary_key=True)
    message_id: str = Field(unique=True)  # WhatsApp message ID
    timestamp: str
    processed_at: datetime = Field(default_factory=datetime.utcnow) 

class UserState(SQLModel, table=True):
    """Store user state for multi-step interactions"""
    id: int = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    state: str  # "awaiting_report"
    active_pdf_id: Optional[int] = None  # Store the active PDF document ID
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Feedback(SQLModel, table=True):
    """Store user feedback"""
    id: int = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    user_name: str
    content: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)

class BugReport(SQLModel, table=True):
    """Store bug reports"""
    id: int = Field(default=None, primary_key=True)
    user_id: str = Field(index=True)
    user_name: str
    content: str
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="open")  # open, in_progress, resolved 