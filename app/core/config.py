# app/core/config.py

import logging
import sys
import os

# Check if running in cloud environment (like Azure)
# If not, assume local development and try to load .env
if os.getenv("WEBSITE_SITE_NAME") is None:
    try:
        from dotenv import load_dotenv

        # Load environment variables from .env file in the project root
        dotenv_path = os.path.join(
            os.path.dirname(__file__), "..", "..", ".env"
        )  # Assumes .env is in project root
        load_dotenv(dotenv_path=dotenv_path, override=True)
    except ImportError:
        print(
            "python-dotenv not found or .env file missing, skipping load_dotenv(). Relying on system environment variables."
        )
    except Exception as e:
        print(f"Error loading .env file: {e}")


class Settings:
    """Simple settings object to hold configuration values"""

    def __init__(self):
        self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./pdf_assistant.db")
        self.TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "sqlite:///./test.db")
        self.UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
        self.VERSION = os.getenv("VERSION", "v22.0")
        self.OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        self.LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
        self.LANGCHAIN_TRACING = os.getenv("LANGCHAIN_TRACING", "true")
        self.LANGCHAIN_PROJECT = os.getenv(
            "LANGCHAIN_PROJECT", "whatsapp-pdf-assistant"
        )
        if not self.OPENAI_API_KEY:
            logging.error("CRITICAL: OPENAI_API_KEY environment variable not set.")

        # Check Twilio settings
        self.TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

        if not self.TWILIO_ACCOUNT_SID:
            logging.warning("TWILIO_ACCOUNT_SID environment variable not set.")
        if not self.TWILIO_AUTH_TOKEN:
            logging.warning("TWILIO_AUTH_TOKEN environment variable not set.")
        if not self.TWILIO_PHONE_NUMBER:
            logging.warning("TWILIO_PHONE_NUMBER environment variable not set.")


def configure_logging():
    """Configure application logging"""
    # Set pypdf logger to ERROR
    logging.getLogger("pypdf").setLevel(logging.ERROR)

    # Suppress cryptography deprecation warnings
    import warnings
    from cryptography.utils import CryptographyDeprecationWarning

    warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )


# Create global settings instance
settings = Settings()
