from sqlmodel import SQLModel, Field
from datetime import datetime

class PDFDocument(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    filename: str
    content: str
    upload_date: datetime = Field(default_factory=datetime.utcnow)
    user_id: str  # WhatsApp user ID 