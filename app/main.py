# app/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from app.core.pdf_processor import PDFProcessor
from app.core.whatsapp_client import WhatsAppClient
import os
from dotenv import load_dotenv
import logging
from sqlmodel import Session
from app.models import PDFDocument, ProcessedMessage
from app.core.database import engine, init_db

load_dotenv()

app = FastAPI()
pdf_processor = PDFProcessor()

# Initialize the database
init_db()

whatsapp_client = WhatsAppClient(
    token=os.getenv("WHATSAPP_TOKEN", ""),
    phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
)


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
        text = pdf_processor.extract_text(file_path)
        return {"message": "PDF processed successfully", "text_length": len(text)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/webhook")
async def verify_webhook(request: Request):
    """Verify webhook for WhatsApp API"""
    verify_token = os.getenv("VERIFY_TOKEN")
    
    # Get query parameters
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == verify_token:
            if challenge:
                # Return the challenge value directly, not as JSON
                return int(challenge)
            return "OK"
        raise HTTPException(status_code=403, detail="Invalid verify token")
    
    raise HTTPException(status_code=400, detail="Invalid request")


@app.post("/webhook")
async def webhook(request: Request):
    """Handle incoming webhook events from WhatsApp"""
    try:
        body = await request.json()
        logging.info(f"Received webhook body: {body}")

        # Add this validation check back
        if not body.get("object") or body.get("object") != "whatsapp_business_account":
            raise HTTPException(status_code=400, detail="Invalid webhook body")

        message_data = extract_message_data(body)
        if not message_data:
            return {"status": "no_message"}

        # Check if message was already processed
        with Session(engine) as session:
            message_id = message_data.get("message_id")
            if message_id:
                existing = session.query(ProcessedMessage).filter_by(message_id=message_id).first()
                if existing:
                    logging.info(f"Skipping already processed message: {message_id}")
                    return {"status": "already_processed"}

        # Initialize WhatsApp client
        whatsapp = whatsapp_client

        # Handle document (PDF) messages
        if message_data.get("type") == "document":
            document = message_data.get("document", {})
            if document.get("mime_type") == "application/pdf":
                # Store PDF metadata in database
                with Session(engine) as session:
                    pdf_doc = PDFDocument(
                        filename=document.get("filename"),
                        content="",  # Will be updated after processing
                        user_id=message_data.get("from"),
                        whatsapp_file_id=document.get("id")  # Store the WhatsApp file ID
                    )
                    session.add(pdf_doc)
                    session.commit()  # Regular commit instead of await

                # Send confirmation message
                await whatsapp.send_message(
                    message_data["from"],
                    f"Received your PDF: {document.get('filename')}. Processing..."
                )
                return {"status": "success", "type": "document"}

        # Handle text messages
        elif message_data.get("type") == "text":
            message_text = message_data.get("text", "").lower()
            if message_text.startswith('/help'):
                response = """Available commands:
- /help: Show this help message
- Send a PDF file to analyze it
- Ask questions about your PDF"""
            else:
                response = f"Hi {message_data['name']}! 👋\nI'm your PDF Assistant. Send me a PDF file or use /help to see what I can do."
            
            if message_data.get("from"):  # Only send if we have a valid recipient
                await whatsapp.send_message(message_data["from"], response)
            return {"status": "success", "type": "text"}

        # After processing, store the message ID
        with Session(engine) as session:
            processed = ProcessedMessage(
                message_id=message_id,
                timestamp=message_data.get("timestamp")
            )
            session.add(processed)
            session.commit()

        return {"status": "success"}

    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logging.error(f"Error in webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

def extract_message_data(body: dict) -> dict:
    """Extract relevant message data from webhook payload"""
    try:
        entry = body["entry"][0]
        changes = entry["changes"][0]
        value = changes["value"]

        # Early return for status updates
        if "statuses" in value:
            logging.info("Received status update - skipping")
            return {}

        # Early return if no messages
        if "messages" not in value:
            logging.info("No messages in payload - skipping")
            return {}

        message = value["messages"][0]
        
        # Check for duplicate messages using timestamp
        timestamp = message.get("timestamp")
        if timestamp:
            # You might want to store processed message timestamps
            # to prevent duplicate processing
            logging.info(f"Processing message with timestamp: {timestamp}")

        return {
            "type": message.get("type"),
            "from": message.get("from"),
            "name": value.get("contacts", [{}])[0].get("profile", {}).get("name"),
            "text": message.get("text", {}).get("body") if message.get("type") == "text" else None,
            "document": message.get("document") if message.get("type") == "document" else None,
            "timestamp": timestamp
        }
    except (KeyError, IndexError):
        logging.info(f"Received non-message webhook event: {body}")
        return {}

if __name__ == "__main__":
    import uvicorn
    print("Starting server...")
    print("Token:", os.getenv("WHATSAPP_TOKEN")[:10] + "...")  # Show just first 10 chars
    print("Phone ID:", os.getenv("WHATSAPP_PHONE_NUMBER_ID"))
    print("Verify Token:", os.getenv("VERIFY_TOKEN"))
    uvicorn.run(app, host="0.0.0.0", port=8000)

