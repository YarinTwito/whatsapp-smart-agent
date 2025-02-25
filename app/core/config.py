import logging
import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings:
    """Simple settings object to hold configuration values"""
    def __init__(self):
        self.WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
        self.WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pdf_assistant.db")
        self.TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")
        self.UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
        self.VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
        self.VERSION = os.getenv("VERSION", "v22.0")

def configure_logging():
    """Configure application logging"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

# Create global settings instance
settings = Settings()