# app/main.py

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Depends
from app.core.pdf_processor import PDFProcessor
from app.core.whatsapp_client import WhatsAppClient
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
pdf_processor = PDFProcessor()

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
    """Handle incoming WhatsApp messages"""
    body = await request.json()
    
    # Log the incoming body for debugging
    print("Received webhook body:", body)
    
    try:
        # Check if this is a status update
        if body.get("entry") and body["entry"][0].get("changes"):
            value = body["entry"][0]["changes"][0].get("value", {})
            if value.get("statuses"):
                # Return 200 OK for status updates
                return {"status": "success"}
        
        if not whatsapp_client.is_valid_message(body):
            print("Invalid message format")
            print("Body structure:", body)
            return {"status": "success"}  # Return 200 OK for invalid messages
        
        # Extract message data
        message_data = await whatsapp_client.extract_message_data(body)
        print("Extracted message data:", message_data)
        
        # Get the message text
        message_text = message_data['message_body'].lower()
        
        # Handle different commands
        if message_text.startswith('/help'):
            response = """Available commands:
- /help: Show this help message
- Send a PDF file to analyze it
- Ask questions about your PDF"""
        else:
            response = f"Hi {message_data['name']}! 👋\nI'm your PDF Assistant. Send me a PDF file or use /help to see what I can do."
        
        # Send response back to user
        print(f"Sending response to {message_data['wa_id']}: {response}")
        await whatsapp_client.send_message(message_data['wa_id'], response)
        
        return {"status": "success"}
    except Exception as e:
        print(f"Error in webhook: {str(e)}")
        # Return 200 OK even for errors to acknowledge receipt
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    print("Starting server...")
    print("Token:", os.getenv("WHATSAPP_TOKEN")[:10] + "...")  # Show just first 10 chars
    print("Phone ID:", os.getenv("WHATSAPP_PHONE_NUMBER_ID"))
    print("Verify Token:", os.getenv("VERIFY_TOKEN"))
    uvicorn.run(app, host="0.0.0.0", port=8000)
