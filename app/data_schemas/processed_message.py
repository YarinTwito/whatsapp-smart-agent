# app/data_schemas/processed_message.py

from sqlmodel import SQLModel, Field
from datetime import datetime

class ProcessedMessage(SQLModel, table=True):
    id: int = Field(default=None, primary_key=True)
    message_id: str = Field(unique=True)  # WhatsApp message ID
    timestamp: str
    processed_at: datetime = Field(default_factory=datetime.utcnow) 