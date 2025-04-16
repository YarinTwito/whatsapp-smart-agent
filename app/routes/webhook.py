# app/routes/webhook.py

from fastapi import APIRouter, File, UploadFile, Request, HTTPException
from app.services.webhook_service import WebhookService
from app.core.pdf_processor import PDFProcessor
from app.core.whatsapp_client import WhatsAppClient
from app.services.langchain_service import LLMService
import os
from pathlib import Path

router = APIRouter()

# Create service instances
pdf_processor = PDFProcessor()
whatsapp = WhatsAppClient(
    token=os.getenv("WHATSAPP_TOKEN", ""),
    phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
)
llm_service = LLMService()
webhook_service = WebhookService(whatsapp, pdf_processor, llm_service)


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        # Extract file extension to give a specific error message
        file_extension = Path(file.filename).suffix if file.filename else ""
        raise HTTPException(
            status_code=400,
            detail=f"Sorry, only PDF files are supported. Cannot accept {file_extension} files.",
        )

    try:
        file_path = await pdf_processor.save_pdf(file)
        return await webhook_service.process_uploaded_pdf(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/webhook")
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
        verify_token=os.getenv("VERIFY_TOKEN"),
    )


@router.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    return await webhook_service.handle_webhook(body)
