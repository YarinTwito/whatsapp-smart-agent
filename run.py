import uvicorn
import logging
from app import create_app
from app.core.config import configure_logging

configure_logging()

app = create_app()

if __name__ == "__main__":
    # Start the FastAPI server
    logging.info("FastAPI server starting...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
