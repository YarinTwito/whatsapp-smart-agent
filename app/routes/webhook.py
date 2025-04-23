# app/routes/webhook.py

from fastapi import APIRouter, File, UploadFile, Request, HTTPException, Response, Form
from app.services.webhook_service import WebhookService
from app.core.pdf_processor import PDFProcessor
from app.services.langchain_service import LLMService
import os
from app.core.twilio_whatsapp_client import TwilioWhatsAppClient
from pathlib import Path
import traceback
import logging

router = APIRouter()


TW_SID   = os.environ["TWILIO_ACCOUNT_SID"]
TW_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
TW_FROM  = os.environ.get("TWILIO_PHONE_NUMBER")

wa_client = TwilioWhatsAppClient(TW_SID, TW_TOKEN, TW_FROM)

# Create service instances
pdf_processor = PDFProcessor(wa_client=wa_client)
llm_service = LLMService()
webhook_service = WebhookService(wa_client, pdf_processor, llm_service)


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...)):
    try:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            file_extension = Path(file.filename).suffix if file.filename else ""
            raise HTTPException(
                status_code=400,
                detail=f"Sorry, only PDF files are supported. Cannot accept {file_extension} files.",
            )

        file_path = await pdf_processor.save_pdf(file)
        return await webhook_service.process_uploaded_pdf(file_path)
    except HTTPException:
        # Let HTTP exceptions pass through unchanged
        raise
    except Exception as e:
        # Only convert other exceptions to 500 errors
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/webhook")
async def webhook(request: Request):
    logger = logging.getLogger(__name__)

    form = await request.form()
    logger.info(f"Received form: {form}")

    if "From" not in form:
        return Response(status_code=400, content="Missing From")

    wa_id     = form.get("WaId") or form["From"].replace("whatsapp:", "").lstrip("+")
    num_media = int(form.get("NumMedia", "0"))

    # Media path
    if num_media:
        content_type = form["MediaContentType0"]
        sid          = form.get("MessageSid")          # for logging
        link         = form["MediaUrl0"]

        message_data = {
            "type":     "document" if content_type == "application/pdf" else "image",
            "from":     wa_id,
            "name":     form.get("ProfileName", ""),
            "document": {
                "sid":       sid,
                "mime_type": content_type,
                "filename":  "",        # will be filled after download
                "link":      link,
            },
        }
        await webhook_service.handle_document(message_data)
        return Response(status_code=200)

    # Text path
    body = form.get("Body")
    if not body:
        return Response(status_code=204)

    await webhook_service.handle_text(
        {"from": wa_id, "name": form.get("ProfileName", ""), "message_body": body}
    )
    return Response(status_code=200)

