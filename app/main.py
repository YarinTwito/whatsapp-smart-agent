# app/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from app.core.pdf_processor import PDFProcessor
from app.core.whatsapp_client import WhatsAppClient
import os
from dotenv import load_dotenv
import logging
from sqlmodel import Session, select
from app.data_schemas import PDFDocument, ProcessedMessage
from app.core.database import engine, init_db
from app.services.langchain_service import LLMService

# Add debug print
print("Current directory:", os.getcwd())
load_dotenv()
print("Env vars loaded:", bool(os.getenv("WHATSAPP_TOKEN")))

app = FastAPI()
pdf_processor = PDFProcessor()

# Initialize the database
init_db()

# debug print
token = os.getenv("WHATSAPP_TOKEN", "")
phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
print(f"Loading WhatsApp token: {token[:10]}... Phone ID: {phone_number_id}")

whatsapp_client = WhatsAppClient(
    token=token,
    phone_number_id=phone_number_id
)

# Initialize LLM service
llm_service = LLMService()

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

        # Store the processed message first
        with Session(engine) as session:
            message_id = message_data.get("message_id")
            if message_id:
                # Check if message was already processed
                existing = session.exec(
                    select(ProcessedMessage).where(ProcessedMessage.message_id == message_id)
                ).first()
                if existing:
                    logging.info(f"Skipping already processed message: {message_id}")
                    return {"status": "already_processed"}
                
                # Add to processed messages
                processed = ProcessedMessage(
                    message_id=message_id,
                    timestamp=str(message_data.get("timestamp", ""))
                )
                session.add(processed)
                session.commit()

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
                        whatsapp_file_id=document.get("id")
                    )
                    session.add(pdf_doc)
                    session.commit()
                    
                    # Add debug logging
                    print(f"Stored PDF document with ID: {pdf_doc.id}")

                    # Process the document with LangChain
                    try:
                        # Get the PDF content (you'll need to implement this)
                        pdf_content = await pdf_processor.get_pdf_content(document)
                        
                        # Process with LangChain
                        await llm_service.process_document(pdf_content, str(pdf_doc.id))
                        
                        # Update the document content in database
                        pdf_doc.content = pdf_content
                        session.add(pdf_doc)
                        session.commit()
                        
                        print(f"Successfully processed document {pdf_doc.id} with LangChain")
                    except Exception as e:
                        print(f"Error processing document: {str(e)}")
                        raise HTTPException(status_code=500, detail=str(e))

                # Send confirmation message
                await whatsapp.send_message(
                    message_data["from"],
                    f"Received your PDF: {document.get('filename')}. Processing..."
                )
                return {"status": "success", "type": "document"}

        # Handle text messages
        elif message_data.get("type") == "text":
            message_text = message_data.get("text", "").lower()
            user_id = message_data.get("from")
            
            # Get the latest PDF document for this user
            with Session(engine) as session:
                pdf_doc = session.exec(
                    select(PDFDocument)
                    .where(PDFDocument.user_id == user_id)
                    .order_by(PDFDocument.upload_date.desc())
                ).first()
            
            if pdf_doc and message_text:
                # Get answer from LLM
                answer = await llm_service.get_answer(message_text, str(pdf_doc.id))
                await whatsapp.send_message(user_id, answer)
            else:
                # Send default response if no PDF found
                response = f"Hi {message_data['name']}! 👋\nPlease send me a PDF file first."
                await whatsapp.send_message(user_id, response)

        logging.info(f"Processing message with ID: {message_data.get('message_id')}")
        logging.info(f"Message data: {message_data}")

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
            "timestamp": timestamp,
            "message_id": message.get("id")
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

