# Empty file to make the directory a Python package

from fastapi import FastAPI
from app.core.config import settings, configure_logging
from app.core.database import init_db
from app.routes.webhook import router as webhook_router

def create_app():
    # Initialize FastAPI app
    app = FastAPI(title="WhatsApp PDF Assistant")
    
    # Configure logging
    configure_logging()
    
    # Initialize database
    init_db()
    
    # Register routes
    app.include_router(webhook_router)
    
    @app.get("/health")
    async def health_check():
        return {"status": "healthy"}
    
    @app.get("/")
    def read_root():
        return {"message": "Hello, Whatsapp PDF Assistant"}
    
    return app
