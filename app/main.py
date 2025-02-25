# app/main.py

from fastapi import FastAPI, File, UploadFile, Request, HTTPException
from app.core.pdf_processor import PDFProcessor
from app.core.whatsapp_client import WhatsAppClient
from app.core.database import init_db, engine
from app.services.langchain_service import LLMService
from app.services.webhook_service import WebhookService
import logging
import os
from dotenv import load_dotenv
import uvicorn

# Configure logging and load environment variables
logging.basicConfig(level=logging.INFO)
load_dotenv()
logging.info(f"Environment variables loaded: {bool(os.getenv('WHATSAPP_TOKEN'))}")

# Create and configure the FastAPI app
app = FastAPI()

# Initialize the database
init_db()

# Initialize services
pdf_processor = PDFProcessor()
whatsapp = WhatsAppClient(
    token=os.getenv("WHATSAPP_TOKEN", ""),
    phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
)
llm_service = LLMService()
webhook_service = WebhookService(whatsapp, pdf_processor, llm_service)

# Define routes
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
def read_root():
    return {"message": "Hello, Whatsapp PDF Assistant"}

@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        file_path = await pdf_processor.save_pdf(file)
        return await webhook_service.process_uploaded_pdf(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/webhook")
async def verify_webhook(request: Request):
    # Get query parameters
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    
    return await webhook_service.verify_webhook(
        mode=mode, 
        token=token, 
        challenge=challenge,
        verify_token=os.getenv("VERIFY_TOKEN")
    )

@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    return await webhook_service.handle_webhook(body)

# Run the app if executed directly
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

